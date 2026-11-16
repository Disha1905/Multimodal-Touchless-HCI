"""Application controller: camera -> hand/face analysis -> policy -> desktop actions."""
from __future__ import annotations
import threading, time
from collections import deque
from config.profiles import CONTEXT_GESTURES
from core import context
from core.actions import ActionDispatcher
from core.policy import EventPolicy
from modules.hand import AdaptiveSmoother
from modules.perf import FpsMeter
from modules.voice import VoiceListener


def default_beep(kind: str):
    """Short audible cue (Windows). kind: on | off | error."""
    try:
        import winsound
    except ImportError:
        return
    seq = {"on": [(880, 110), (1320, 160)], "off": [(1320, 110), (660, 160)], "error": [(300, 300)]}[kind]

    def run():
        for f, d in seq:
            winsound.Beep(f, d)
    threading.Thread(target=run, daemon=True).start()


class Controller:
    ACTIVE_MARGIN = 0.15  # fraction of frame ignored at edges for cursor mapping

    def __init__(self):
        self.policy = EventPolicy()
        self.actions = ActionDispatcher()
        self.actions.prepare = self._prepare_target
        self.actions.focus_target = self._focus_target_window
        self.smoother = AdaptiveSmoother()
        self._last_cursor_px = None
        self.fps = FpsMeter()
        self.camera = None
        self.hand = None
        self.face = None
        self.face_events = None
        self.face_enabled = False
        self.face_sensitivity = 1.0
        self.alert = None                         # (text, monotonic time, kind) shown briefly on the dashboard
        self.beep = default_beep
        self.voice_log: deque = deque(maxlen=6)   # (time, heard text, result)
        self._frame_n = 0
        self.camera_index = 0
        self.camera_fps = 30
        self.profile = "Default"
        self.auto_profile = True
        self.manual_profile = "Default"
        self.target_hwnd: int | None = None      # explicitly selected target window (None = automatic)
        self.last_external: dict | None = None   # last foreground window that is not the dashboard
        self.status = {"gesture": "-", "face": "-", "voice": "Stopped", "profile": "Default", "heard": "",
                       "fingers": "-", "window": "Unknown window", "process": "Unknown process"}
        self.last_jpeg = None
        self._face_ev_t = 0.0
        self._stop = threading.Event()
        self._t = None
        self.voice = VoiceListener(self._on_voice, lambda s: self.status.__setitem__("voice", s), self._on_heard)

    # ---- lifecycle ----
    def start(self, camera_index: int | None = None, fps: int | None = None) -> bool:
        if self._t and self._t.is_alive():
            return True
        from modules.camera import Camera
        from modules.hand import HandTracker
        if camera_index is not None:
            self.camera_index = camera_index
        if fps is not None:
            self.camera_fps = fps
        self.camera = Camera(self.camera_index, fps=self.camera_fps)
        if not self.camera.start():
            return False
        self.hand = HandTracker()
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return True

    def stop(self):
        self._stop.set()
        self.set_controls(False)
        if self._t:
            self._t.join(timeout=2)
        if self.camera:
            self.camera.stop()
        for o in (self.hand, self.face):
            if o:
                o.close()
        self.camera = self.hand = self.face = None
        self.face_enabled = False
        self.voice.stop()

    @property
    def running(self) -> bool:
        return bool(self._t and self._t.is_alive())

    def set_controls(self, on: bool):
        self.policy.controls_enabled = on
        self.actions.enabled = on
        if not on:
            self.actions.release_drag()
            self.smoother.reset()
            self._last_cursor_px = None

    def set_face(self, on: bool):
        self.face_enabled = on
        if on and self.face is None:
            from modules.face import FaceTracker, FaceEvents
            self.face, self.face_events = FaceTracker(), FaceEvents(self.face_sensitivity)
        if not on and self.face:
            self.face.close()
            self.face = None

    def recalibrate_face(self):
        if self.face_events:
            self.face_events.reset()

    # ---- window targeting ----
    def _target_hwnd(self):
        return self.target_hwnd or (self.last_external or {}).get("hwnd")

    def _prepare_target(self):
        """Keyboard shortcuts must not land in the dashboard: redirect to the target window if it is in front."""
        _, title, _ = context.foreground_info()
        if context.is_own_window(title):
            want = self._target_hwnd()
            if want and context.focus_window(want):
                time.sleep(0.15)

    def _focus_target_window(self) -> bool:
        hwnd, title, _ = context.foreground_info()
        want = self.target_hwnd
        if want is None and context.is_own_window(title):
            want = (self.last_external or {}).get("hwnd")
        if want and want != hwnd and context.focus_window(want):
            time.sleep(0.15)
            return True
        return False

    # ---- main loop ----
    def _loop(self):
        import cv2
        from modules import hand as H
        last_id = -1
        while not self._stop.is_set():
            fid = self.camera.frame_id
            frame = self.camera.read() if fid != last_id else None
            if frame is None:                       # no new camera frame yet: wait instead of re-processing the old one
                time.sleep(0.005)
                continue
            last_id = fid
            frame = cv2.flip(frame, 1)  # mirrored preview
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            infer_rgb = cv2.resize(rgb, (320, 240))
            self.fps.tick()
            lm, raw = self.hand.process(infer_rgb)
            if lm is not None:
                self.hand.draw(frame, raw)
                self.status["fingers"] = " ".join(f"{n}{v}" for n, v in zip("TIMRP", H.finger_states(lm)))
                kind, label = H.classify(lm)
                self._handle_hand(kind, label, lm)
            else:
                self._handle_hand("none", None, None)
                self.status["gesture"] = "no hand"
                self.status["fingers"] = "-"
            self._frame_n += 1
            if self.face_enabled and self.face:   # face events are slow: every 2nd frame
                self._handle_face(infer_rgb)
            hwnd, title, proc = context.foreground_info()
            self.status["window"], self.status["process"] = title or "Unknown window", proc or "Unknown process"
            if hwnd and not context.is_own_window(title):
                self.last_external = {"hwnd": hwnd, "title": title, "process": proc}
                if self.auto_profile:
                    self.profile = context.profile_for(title, proc)
            if not self.auto_profile:
                self.profile = self.manual_profile
            self.status["profile"] = self.profile
            self._draw_overlays(frame)
            small = cv2.resize(frame, (480, int(frame.shape[0] * 480 / frame.shape[1])))
            ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                self.last_jpeg = buf.tobytes()

    def _draw_overlays(self, frame):
        import cv2
        if self.voice.active:
            cv2.circle(frame, (24, 24), 9, (0, 0, 255), -1)
            cv2.putText(frame, "MIC ON", (42, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        if self.face_enabled:
            cv2.putText(frame, f"Face: {self.status['face']}", (10, frame.shape[0] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (120, 220, 120), 2)
            fe = self.face_events
            p = fe.hold_progress("mouth_open") if fe and fe.calibrated else 0.0
            if 0.05 < p < 1.0:                    # feedback while the mouth is being held open
                w = frame.shape[1]
                cv2.rectangle(frame, (10, 50), (10 + int((w - 20) * p), 62), (0, 200, 255), -1)
                cv2.putText(frame, "keep mouth open...", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

    def _handle_hand(self, kind, label, lm):
        stable = self.policy.stable(f"{kind}:{label}")
        if stable is None:
            return
        self.status["gesture"] = f"{label}" if label else "-"
        if kind != "global" or label != "drag":
            self.actions.release_drag()  # safe release when the drag pose ends
        if kind == "none":
            self.smoother.reset()
            self._last_cursor_px = None
            return
        if kind == "context":
            act = CONTEXT_GESTURES.get(self.profile, {}).get(label)
            if act and self.policy.allow(f"ctx:{label}"):
                self.actions.shortcut(act, source=label)
            return
        # global poses
        if label in ("cursor", "drag") and lm:
            if label == "drag":
                self.actions.start_drag()          # mouse button down, then the hand moves the cursor
            self._move_cursor(lm)
            return
        if label == "left_click" and self.policy.allow("left_click"):
            self.actions.click("left")
        elif label == "right_click" and self.policy.allow("right_click"):
            self.actions.click("right")
        elif label == "scroll_up" and self.policy.allow("scroll"):
            self.actions.scroll(120)
        elif label == "scroll_down" and self.policy.allow("scroll"):
            self.actions.scroll(-120)

    def _move_cursor(self, lm):
        m = self.ACTIVE_MARGIN
        x = min(max((lm[8][0] - m) / (1 - 2 * m), 0), 1)
        y = min(max((lm[8][1] - m) / (1 - 2 * m), 0), 1)
        sx, sy = self.smoother.update(x, y)
        w, h = self.actions.screen_size()
        nx, ny = int(sx * (w - 1)), int(sy * (h - 1))
        if self._last_cursor_px is None or abs(nx - self._last_cursor_px[0]) > 1 or abs(ny - self._last_cursor_px[1]) > 1:
            self._last_cursor_px = (nx, ny)
            self.actions.move(nx, ny)

    def _handle_face(self, rgb):
        from modules.face import metrics
        lm = self.face.process(rgb)
        fe = self.face_events
        if lm is None:
            self.status["face"] = "no face detected"
            return
        fe.sensitivity = self.face_sensitivity
        events = fe.update(metrics(lm), time.monotonic())
        if not fe.calibrated or time.monotonic() - self._face_ev_t > 1.5:
            self.status["face"] = fe.note
        for ev in events:
            self._apply_face_event(ev)

    def _apply_face_event(self, ev: str):
        self._face_ev_t = time.monotonic()
        self.status["face"] = ev.replace("_", " ")
        if ev == "mouth_open":
            self.toggle_voice()                        # no desktop input -> allowed while paused
        elif ev in ("left_wink", "right_wink") and self.actions.enabled:
            self._focus_target_window()
            self.actions.click("left" if ev == "left_wink" else "right")
        # blink / eyebrow: detection only (shown on screen, no action)

    # ---- voice ----
    def _announce(self, text: str, kind: str):
        self.alert = (text, time.monotonic(), kind)
        self.beep(kind)

    def set_voice(self, on: bool) -> bool:
        """Start/stop continuous listening with an audible + on-screen alert."""
        if on:
            ok = self.voice.start()
            self._announce("Microphone ON - listening for commands" if ok
                           else "Microphone unavailable - check permissions", "on" if ok else "error")
            return ok
        self.voice.stop()
        self._announce("Microphone OFF - voice listening stopped", "off")
        return True

    def toggle_voice(self):
        """Non-blocking toggle (used by the mouth-open gesture)."""
        threading.Thread(target=lambda: self.set_voice(not self.voice.active), daemon=True).start()

    def _on_heard(self, text: str, res):
        if res is None:
            result = "not a command"
        elif not self.actions.enabled:
            result = f"{res[0].replace('_', ' ')} - blocked (controls paused)"
        else:
            result = f"{res[0].replace('_', ' ')} - done"
        self.voice_log.appendleft((time.strftime("%H:%M:%S"), text, result))

    def push_to_talk(self):
        """Listen for ONE command (no continuous listening)."""
        threading.Thread(target=self.voice.listen_once, daemon=True).start()

    def _on_voice(self, cid: str, arg):
        self.status["heard"] = cid if not arg else f"{cid}: {arg}"
        if not self.actions.enabled:
            return                                  # desktop input blocked while paused
        keyboard = {"save", "go_back", "refresh", "new_tab", "close_tab", "next_slide", "prev_slide", "search"}
        media = {"play_pause", "next_track", "prev_track", "mute"}
        if cid == "click":
            self.actions.click("left")
        elif cid == "right_click":
            self.actions.click("right")
        elif cid == "scroll_up":
            self.actions.scroll(300)
        elif cid == "scroll_down":
            self.actions.scroll(-300)
        elif cid in media:
            self.actions.shortcut(cid, source="voice")   # media method decides whether to focus the target
        elif cid in keyboard:
            self._focus_target_window()
            if cid == "search":
                self.actions.shortcut("focus_address", source="voice")
                if arg:
                    time.sleep(0.15)
                    self.actions.b.write(arg, interval=0.01)
                    self.actions.b.press("enter")
            else:
                self.actions.shortcut(cid, source="voice")

