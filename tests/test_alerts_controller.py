from core.alerts import AlertCenter
from core.actions import ActionDispatcher
from core import controller as C
from tests.test_policy_actions import Fake
from tests.helpers import hand


def make(monkeypatch):
    f = Fake()
    monkeypatch.setattr(C, "ActionDispatcher", lambda: ActionDispatcher(f))
    t = [0.0]
    ctl = C.Controller()
    ctl.beep = lambda kind: None
    ctl.policy.clock = lambda: t[0]
    ctl.set_controls(True)
    return ctl, f, t


def feed(ctl, t, secs, kind, label, lm, step=0.05):
    end = t[0] + secs
    while t[0] < end:
        ctl._handle_hand(kind, label, lm)
        t[0] += step


def test_alert_center_sequence_expiry_and_sound():
    t, heard = [0.0], []
    a = AlertCenter(sound=heard.append, clock=lambda: t[0])
    assert not a.active() and a.seq == 0
    a.push("VOICE LISTENING", "on")
    assert a.seq == 1 and a.active() and heard == ["on"]
    t[0] = 5.0
    assert not a.active()
    a.sound_enabled = False
    a.push("Voice listening stopped", "off")
    assert a.seq == 2 and heard == ["on"]


class FakeVoice:
    def __init__(self, ok=True): self.active, self.ok, self.last_heard = False, ok, ""
    def start(self):
        self.active = self.ok
        return self.ok
    def stop(self): self.active = False


def test_start_and_stop_voice_raise_alerts(monkeypatch):
    ctl, _, _ = make(monkeypatch)
    ctl.voice = FakeVoice()
    assert ctl.set_voice(True) is True
    assert ctl.alert[2] == "on" and "ON" in ctl.alert[0]
    ctl.set_voice(False)
    assert ctl.alert[2] == "off"


def test_microphone_failure_raises_error_alert(monkeypatch):
    ctl, _, _ = make(monkeypatch)
    ctl.voice = FakeVoice(ok=False)
    assert ctl.set_voice(True) is False
    assert ctl.alert[2] == "error"


def test_mouth_open_event_toggles_voice_even_when_controls_paused(monkeypatch):
    ctl, _, _ = make(monkeypatch)
    ctl.set_controls(False)
    calls = []
    ctl.toggle_voice = lambda: calls.append(1)
    ctl._apply_face_event("mouth_open")
    assert calls == [1]


def test_c3_next_track_needs_a_hold_and_fires_once(monkeypatch):
    ctl, f, t = make(monkeypatch)
    ctl.profile = "Media"
    sent = []
    ctl.actions.vk_sender = sent.append
    lm = hand(pinky=1)
    feed(ctl, t, 0.08, "context", "C3", lm)
    assert sent == []
    feed(ctl, t, 0.4, "context", "C3", lm)
    assert sent == ["next_track"]
    feed(ctl, t, 0.3, "global", "neutral", hand())
    feed(ctl, t, 1.0, "context", "C3", lm)
    assert sent == ["next_track", "next_track"]


def test_c3_does_nothing_outside_media_profile(monkeypatch):
    ctl, f, t = make(monkeypatch)
    ctl.profile = "Default"
    sent = []
    ctl.actions.vk_sender = sent.append
    feed(ctl, t, 1.0, "context", "C3", hand(pinky=1))
    assert sent == [] and not f.calls
