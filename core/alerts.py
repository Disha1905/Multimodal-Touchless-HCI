"""Short audible + visual notices (for example 'voice listening started').

The controller records the latest alert here; the dashboard shows it as a banner/toast and the camera
preview draws it on the video, so the user notices it even without looking at the dashboard."""
from __future__ import annotations
import threading, time

# kind -> list of (frequency Hz, duration ms)
TONES = {"on": [(880, 110), (1175, 160)], "off": [(660, 110), (440, 160)],
         "once": [(988, 140)], "error": [(300, 320)]}
COLORS_BGR = {"on": (60, 170, 60), "off": (110, 110, 110), "once": (200, 120, 40), "error": (50, 50, 200)}


def beep(kind: str) -> None:
    """Play the tone for `kind` without blocking the caller. Silent where winsound is unavailable."""
    def run():
        try:
            import winsound
            for f, d in TONES.get(kind, TONES["once"]):
                winsound.Beep(f, d)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


class AlertCenter:
    SHOW_S = 3.0

    def __init__(self, sound=beep, clock=time.monotonic):
        self.sound, self.clock = sound, clock
        self.seq = 0                      # increases with every alert; the dashboard toasts each new one
        self.text, self.kind, self.t = "", "once", -1e9
        self.sound_enabled = True

    def push(self, text: str, kind: str = "once") -> None:
        self.seq += 1
        self.text, self.kind, self.t = text, kind, self.clock()
        if self.sound_enabled and self.sound:
            self.sound(kind)

    def active(self) -> bool:
        return self.clock() - self.t < self.SHOW_S

    def draw(self, frame) -> None:
        """Draw the current alert as a banner across the top of a BGR frame (no-op when expired)."""
        if not self.active():
            return
        import cv2
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 44), COLORS_BGR.get(self.kind, COLORS_BGR["once"]), -1)
        cv2.putText(frame, self.text, (14, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
