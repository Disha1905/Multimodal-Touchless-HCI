from core.policy import EventPolicy
from core.actions import ActionDispatcher
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


def test_controls_start_paused_and_block_input():
    f = Fake(); a = ActionDispatcher(f)
    assert EventPolicy().controls_enabled is False
    a.move(1, 1); a.click(); a.scroll(1); a.shortcut("save"); a.start_drag()
    assert f.calls == []


def test_enabled_dispatch_and_safe_drag_release():
    f = Fake(); a = ActionDispatcher(f); a.enabled = True
    a.vk_sender = lambda act: f.press("playpause" if act == "play_pause" else act)
    a.shortcut("save"); a.shortcut("play_pause"); a.start_drag()
    a.enabled = False            # paused mid-drag
    a.release_drag()
    assert ("hotkey", ("ctrl", "s")) in f.calls and ("press", "playpause") in f.calls
    assert f.calls[-1] == ("up",)


def test_stability_and_cooldown():
    t = [0.0]
    p = EventPolicy(stable_frames=3, cooldown=1.0, clock=lambda: t[0])
    assert [p.stable("a") for _ in range(3)] == [None, None, "a"]
    assert p.allow("x") and not p.allow("x")
    t[0] = 2.0
    assert p.allow("x")


def test_context_title_beats_process():
    assert context.classify("Relax - JioSaavn - Google Chrome", "chrome.exe") == "media"
    assert context.classify("Docs - Google Chrome", "chrome.exe") == "browser"
    assert context.classify("deck.pptx - PowerPoint", "POWERPNT.EXE") == "presentation"
    assert context.classify("main.py - Visual Studio Code", "Code.exe") == "coding"
    assert context.classify("Untitled", "notepad.exe") == "default"


def test_previous_tab_uses_ctrl_pageup():
    f = Fake(); a = ActionDispatcher(f); a.enabled = True
    assert a.shortcut("prev_tab", source="C2")
    assert f.calls[-1] == ("hotkey", ("ctrl", "pageup"))
    assert a.log[-1][1].startswith("prev_tab")


def test_drag_presses_then_moves_cursor_and_releases(monkeypatch):
    from core import controller as C
    from tests.helpers import hand
    f = Fake()
    monkeypatch.setattr(C, "ActionDispatcher", lambda: ActionDispatcher(f))
    ctl = C.Controller()
    ctl.set_controls(True)
    lm = hand(index=1, pinky=1)
    for _ in range(3):
        ctl._handle_hand("global", "drag", lm)
    kinds = [c[0] for c in f.calls]
    assert "down" in kinds and "move" in kinds
    assert kinds.index("down") < kinds.index("move")          # button pressed before the cursor moves
    for _ in range(3):
        ctl._handle_hand("global", "neutral", hand())
    assert f.calls[-1] == ("up",) or ("up",) in f.calls       # released when the pose ends


def test_media_keys_method_uses_system_key():
    f = Fake(); a = ActionDispatcher(f); a.enabled = True
    sent = []
    a.vk_sender = sent.append
    a.shortcut("next_track"); a.shortcut("prev_track"); a.shortcut("play_pause"); a.shortcut("mute")
    assert sent == ["next_track", "prev_track", "play_pause", "mute"]
    assert not f.calls                                   # no keyboard shortcut was typed


def test_media_window_method_focuses_target_and_types_shortcut():
    f = Fake(); a = ActionDispatcher(f); a.enabled = True
    a.media_method = "window"
    focused = []
    a.focus_target = lambda: focused.append(1)
    a.shortcut("play_pause"); a.shortcut("next_track")
    assert focused == [1, 1]
    assert ("press", "space") in f.calls and ("hotkey", ("ctrl", "right")) in f.calls


def test_media_window_method_falls_back_to_system_key_when_no_combo():
    f = Fake(); a = ActionDispatcher(f); a.enabled = True
    a.media_method = "window"
    sent = []
    a.vk_sender = sent.append
    a.shortcut("mute")                                   # mute has no window shortcut by default
    assert sent == ["mute"]


def test_media_blocked_while_paused():
    f = Fake(); a = ActionDispatcher(f)
    sent = []
    a.vk_sender = sent.append
    assert a.shortcut("play_pause") is False and sent == []


def test_keyboard_shortcut_calls_prepare_hook_first():
    f = Fake(); a = ActionDispatcher(f); a.enabled = True
    order = []
    a.prepare = lambda: order.append("prepare")
    a.b = type("B", (Fake,), {"hotkey": lambda self, *k: order.append("hotkey")})()
    a.shortcut("save")
    assert order == ["prepare", "hotkey"]


def test_winkeys_falls_back_to_backend_off_windows(monkeypatch):
    from core import winkeys
    monkeypatch.setattr(winkeys.sys, "platform", "linux")
    f = Fake()
    assert winkeys.send_media("play_pause", f) is True
    assert f.calls[-1] == ("press", "playpause")
    assert winkeys.MEDIA_VK == {"play_pause": 0xB3, "next_track": 0xB0, "prev_track": 0xB1, "mute": 0xAD}


def test_controller_redirects_to_target_when_dashboard_is_in_front(monkeypatch):
    from core import controller as C, context
    f = Fake()
    monkeypatch.setattr(C, "ActionDispatcher", lambda: ActionDispatcher(f))
    ctl = C.Controller()
    ctl.last_external = {"hwnd": 42, "title": "JioSaavn - Chrome", "process": "chrome.exe"}
    focused = []
    monkeypatch.setattr(context, "foreground_info", lambda: (7, "Multimodal Touchless HCI - Google Chrome", "chrome.exe"))
    monkeypatch.setattr(context, "focus_window", lambda h: focused.append(h) or True)
    monkeypatch.setattr("time.sleep", lambda s: None)
    ctl._prepare_target()
    assert focused == [42]
    monkeypatch.setattr(context, "foreground_info", lambda: (9, "Notes", "notepad.exe"))
    focused.clear(); ctl._prepare_target()
    assert focused == []                                  # another app already in front: leave it alone


def test_voice_media_command_uses_media_route(monkeypatch):
    from core import controller as C
    f = Fake()
    monkeypatch.setattr(C, "ActionDispatcher", lambda: ActionDispatcher(f))
    ctl = C.Controller(); ctl.set_controls(True)
    sent = []
    ctl.actions.vk_sender = sent.append
    ctl._on_voice("next_track", None)
    assert sent == ["next_track"]
    ctl.set_controls(False); sent.clear()
    ctl._on_voice("next_track", None)
    assert sent == []
