"""Optional facial interaction (MediaPipe Face Mesh). Interaction events only -- NOT authentication.

Actions: left/right wink = click, mouth held open = voice on/off. Blink and eyebrow raise are detected only.
Design: time-based (not frame-count) holds so behaviour does not depend on FPS; smoothed metrics;
per-user calibration; head-turn guard; per-event cooldowns; mouth hysteresis; adjustable sensitivity."""
from __future__ import annotations
import math, statistics

EYE_A = [33, 160, 158, 133, 153, 144]
EYE_B = [362, 385, 387, 263, 373, 380]
LIP_T, LIP_B = 13, 14
FACE_L, FACE_R, FACE_TOP, FACE_BOT, NOSE = 234, 454, 10, 152, 1
BROW_A, EYE_TOP_A = 105, 159
BROW_B, EYE_TOP_B = 334, 386

YAW_MAX = 0.16          # |nose offset| / face width above which the head is considered turned away
HOLD_S = {"left_wink": 0.0, "right_wink": 0.0, "eyebrow": 0.40, "mouth_open": 0.8}
COOLDOWN_S = {"left_wink": 0.0, "right_wink": 0.0, "eyebrow": 1.0, "mouth_open": 1.5, "blink": 0.3}
MOUTH_ON = 0.06        # mouth gap (fraction of face width) above neutral that counts as "open"


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def ear(lm, idx) -> float:
    p = [lm[i] for i in idx]
    return (_d(p[1], p[5]) + _d(p[2], p[4])) / (2.0 * _d(p[0], p[3]) + 1e-9)


def metrics(lm) -> dict:
    """lm: 468+ (x, y, z) face landmarks from the MIRRORED frame (so 'left' = left of the preview)."""
    fw = _d(lm[FACE_L], lm[FACE_R]) + 1e-9
    fh = _d(lm[FACE_TOP], lm[FACE_BOT]) + 1e-9
    ax = sum(lm[i][0] for i in EYE_A) / 6
    bx = sum(lm[i][0] for i in EYE_B) / 6
    ear_a, ear_b = ear(lm, EYE_A), ear(lm, EYE_B)
    left, right = (ear_a, ear_b) if ax < bx else (ear_b, ear_a)
    return {
        "ear_left": left, "ear_right": right,
        "mouth_open": _d(lm[LIP_T], lm[LIP_B]) / fw,
        "brow": (_d(lm[BROW_A], lm[EYE_TOP_A]) + _d(lm[BROW_B], lm[EYE_TOP_B])) / (2 * fh),
        "yaw": (lm[NOSE][0] - (lm[FACE_L][0] + lm[FACE_R][0]) / 2) / fw,
    }


class FaceEvents:
    """Calibrates on ~2 s of neutral face, then emits discrete events from timestamped metrics."""
    SMOOTH = 0.85   # EMA weight of the newest sample

    def __init__(self, sensitivity: float = 1.0, calib_s: float = 2.0):
        self.sensitivity = sensitivity
        self.calib_s = calib_s
        self.reset()

    def reset(self):
        self.base = None
        self.progress = 0.0
        self.note = "Look straight at the camera with a relaxed face"
        self.debug: dict = {}
        self._t0 = None
        self._samples: list[dict] = []
        self._s: dict | None = None
        self._since: dict[str, float] = {}
        self._fired: dict[str, bool] = {}
        self._last: dict[str, float] = {}
        self._closed_since = None
        self._mouth_latched = False
        self._now = 0.0

    @property
    def calibrated(self) -> bool:
        return self.base is not None

    def hold_progress(self, name: str) -> float:
        """0..1 progress of an event whose condition is currently held (for on-screen feedback)."""
        since = self._since.get(name)
        return 0.0 if since is None else min(1.0, (self._now - since) / HOLD_S[name])

    def _smooth(self, m: dict) -> dict:
        if self._s is None:
            self._s = dict(m)
        else:
            a = self.SMOOTH
            self._s = {k: a * m[k] + (1 - a) * self._s[k] for k in m}
        return self._s

    def _calibrate(self, m: dict, now: float):
        if abs(m["yaw"]) > YAW_MAX:
            self.note = "Face the camera directly to calibrate"
            return
        if self._t0 is None:
            self._t0 = now
        self._samples.append(m)
        self.progress = min(1.0, (now - self._t0) / self.calib_s)
        self.note = f"Calibrating {int(self.progress * 100)}% - keep a relaxed face, eyes open"
        if now - self._t0 >= self.calib_s and len(self._samples) >= 8:
            base = {k: statistics.median(s[k] for s in self._samples) for k in m}
            if base["ear_left"] < 0.12 or base["ear_right"] < 0.12:
                self._t0, self._samples = None, []      # eyes were closed: start over
                self.note = "Keep both eyes open while calibrating"
                return
            self.base, self.progress, self.note = base, 1.0, "Ready"

    def update(self, m: dict, now: float) -> list[str]:
        self._now = now
        m = self._smooth(m)
        if self.base is None:
            self._calibrate(m, now)
            return []
        if abs(m["yaw"]) > YAW_MAX:
            self.note = "Turn to face the camera"
            self._since.clear()
            self._closed_since = None
            return []
        self.note = "Ready"
        b, k = self.base, self.sensitivity
        el, er = m["ear_left"] / b["ear_left"], m["ear_right"] / b["ear_right"]
        closed, wide = 0.78 + 0.08 * k, 0.60
        # mouth-open uses hysteresis: once clearly open it stays "open" until it nearly closes, so small
        # fluctuations do not restart the hold timer (this is what made it feel like it "sometimes misses")
        mouth_gap = m["mouth_open"] - b["mouth_open"]
        on_thr = MOUTH_ON / k
        self._mouth_latched = mouth_gap > (on_thr * 0.55 if self._mouth_latched else on_thr)
        cond = {
            "left_wink": el < closed and er > wide and (er - el) > 0.06,
            "right_wink": er < closed and el > wide and (el - er) > 0.06,
            "mouth_open": self._mouth_latched,
            "eyebrow": m["brow"] / b["brow"] > 1 + 0.15 / k,
        }
        both_closed = el < 0.72 and er < 0.72 and abs(el - er) < 0.06
        self.debug = {"left_eye": round(el, 2), "right_eye": round(er, 2),
                      "mouth": round(mouth_gap, 3), "mouth_needed": round(on_thr, 3),
                      "brow": round(m["brow"] / b["brow"], 2)}
        events: list[str] = []
        # blink = both eyes closed briefly (detection only); it also suppresses winks
        if both_closed:
            if self._closed_since is None:
                self._closed_since = now
            cond["left_wink"] = cond["right_wink"] = False
        elif self._closed_since is not None:
            dur, self._closed_since = now - self._closed_since, None
            if 0.06 <= dur <= 0.5 and now - self._last.get("blink", -9) >= COOLDOWN_S["blink"]:
                self._last["blink"] = now
                events.append("blink")
        for name, on in cond.items():
            if on:
                since = self._since.setdefault(name, now)
                if (not self._fired.get(name) and now - since >= HOLD_S[name]
                        and now - self._last.get(name, -9) >= COOLDOWN_S[name]):
                    self._fired[name] = True
                    self._last[name] = now
                    events.append(name)
            else:
                self._since.pop(name, None)
                self._fired[name] = False
        return events


class FaceTracker:
    def __init__(self):
        import mediapipe as mp
        self._fm = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1, refine_landmarks=False,
            min_detection_confidence=0.6, min_tracking_confidence=0.6)

    def process(self, rgb_frame):
        res = self._fm.process(rgb_frame)
        if not res.multi_face_landmarks:
            return None
        return [(p.x, p.y, p.z) for p in res.multi_face_landmarks[0].landmark]

    def close(self):
        self._fm.close()


