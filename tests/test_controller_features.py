import pytest
from core import controller as C
from core.actions import ActionDispatcher
from modules import screen_ai as S
from core import context


class Fake:
    def __init__(self): self.calls = []
    def size(self): return (1920, 1080)
    def moveTo(self, x, y): self.calls.append(("move", x, y))
    def click(self, button="left"): self.calls.append(("click", button))
    def scroll(self, n): self.calls.append(("scroll", n))
    def mouseDown(self): self.calls.append(("down",))
    def mouseUp(self): self.calls.append(("up",))
    def hotkey(self, *k): self.calls.append(("hotkey", k))
    def press(self, k): self.calls.append(("press", k))


@pytest.fixture
def ctl(monkeypatch):
    f = Fake()
    monkeypatch.setattr(C, "ActionDispatcher", lambda: ActionDispatcher(f))
    c = C.Controller()
    c.beeps = []
    c.beep = c.beeps.append
    c.fake = f
    c.actions.vk_sender = lambda a: f.calls.append(("media", a))
    return c


def test_wink_clicks_only_when_controls_enabled(ctl):
    ctl._apply_face_event("left_wink")
    assert ("click", "left") not in ctl.fake.calls
    ctl.set_controls(True)
    ctl._apply_face_event("left_wink"); ctl._apply_face_event("right_wink")
    assert ("click", "left") in ctl.fake.calls and ("click", "right") in ctl.fake.calls


def test_smile_is_gone_and_never_triggers_anything(ctl):
    ctl.set_controls(True)
    ctl._apply_face_event("smile")
    assert ctl.fake.calls == []
    assert not hasattr(ctl, "smile_action")


def test_blink_and_eyebrow_are_detection_only(ctl):
    ctl.set_controls(True)
    ctl._apply_face_event("blink"); ctl._apply_face_event("eyebrow")
    assert ctl.fake.calls == []
    assert ctl.status["face"] == "eyebrow"


def test_voice_start_and_stop_raise_an_alert_and_a_beep(ctl, monkeypatch):
    monkeypatch.setattr(ctl.voice, "start", lambda: setattr(ctl.voice, "active", True) or True)
    monkeypatch.setattr(ctl.voice, "stop", lambda: setattr(ctl.voice, "active", False))
    assert ctl.set_voice(True)
    assert "ON" in ctl.alert[0] and ctl.alert[2] == "on" and ctl.beeps == ["on"]
    ctl.set_voice(False)
    assert "OFF" in ctl.alert[0] and ctl.beeps == ["on", "off"]


def test_voice_start_failure_reports_error(ctl, monkeypatch):
    monkeypatch.setattr(ctl.voice, "start", lambda: False)
    assert ctl.set_voice(True) is False
    assert ctl.alert[2] == "error" and ctl.beeps == ["error"]


def test_mouth_open_toggles_voice(ctl, monkeypatch):
    called = []
    monkeypatch.setattr(ctl, "toggle_voice", lambda: called.append(1))
    ctl._apply_face_event("mouth_open")                  # allowed even while controls are paused
    assert called == [1]


def test_voice_log_pairs_each_utterance_with_its_result(ctl):
    ctl._on_heard("blah blah", None)
    ctl._on_heard("next track", ("next_track", None))
    ctl.set_controls(True)
    ctl._on_heard("mute", ("mute", None))
    results = [r for _, _, r in reversed(ctl.voice_log)]
    assert results[0] == "not a command"
    assert "blocked" in results[1] and results[2] == "mute - done"


def test_window_label_is_readable():
    assert context.window_label({"title": "Barbaad - JioSaavn", "process": "ApplicationFrameHost.exe"}) == "Barbaad - JioSaavn"
    assert context.window_label({"title": "Inbox", "process": "msedge.exe"}) == "Inbox  —  Edge"
    assert context.window_label({"title": "Docs - Microsoft Edge", "process": "msedge.exe"}) == "Docs - Microsoft Edge"
    long = context.window_label({"title": "x" * 200, "process": "chrome.exe"})
    assert len(long) < 90


def test_ocr_auto_keeps_good_english_without_second_pass(monkeypatch):
    calls = []
    monkeypatch.setattr(S, "ocr", lambda img, lang: calls.append(lang) or ("Hello world", 92.0, ""))
    assert S.ocr_auto(object())[3] == "eng" and calls == ["eng"]


def test_ocr_auto_retries_with_all_languages_for_indic_text(monkeypatch):
    def fake(img, lang):
        return ("xx", 20.0, "") if lang == "eng" else ("ನಮಸ್ಕಾರ ಜಗತ್ತು", 88.0, "")
    monkeypatch.setattr(S, "ocr", fake)
    text, conf, _, used = S.ocr_auto(object())
    assert text.startswith("ನಮ") and "kan" in used and "+" in used


def test_ocr_auto_respects_forced_language(monkeypatch):
    calls = []
    monkeypatch.setattr(S, "ocr", lambda img, lang: calls.append(lang) or ("t", 50.0, ""))
    S.ocr_auto(object(), "hin")
    assert calls == ["hin"]


def test_ocr_auto_falls_back_when_extra_packs_unavailable(monkeypatch):
    def fake(img, lang):
        if "+" in lang:
            raise RuntimeError("no internet")
        return ("weak", 40.0, "")
    monkeypatch.setattr(S, "ocr", fake)
    assert S.ocr_auto(object())[0] == "weak"


def test_screenshot_data_uri_always_renders():
    from PIL import Image
    uri = S.to_data_uri(Image.new("RGB", (2400, 1200), "white"))
    assert uri.startswith("data:image/jpeg;base64,") and len(uri) > 100


def test_system_stats_never_blocks_and_has_both_values():
    import time
    from modules.perf import system_stats
    t = time.time(); s = system_stats()
    assert time.time() - t < 0.5 and "cpu_percent" in s and 0 <= s["memory_percent"] <= 100
