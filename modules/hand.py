"""MediaPipe Hands analysis: finger-state classification into global/context poses."""
from __future__ import annotations
import math

# Landmark indices
WRIST, THUMB_IP, THUMB_TIP, INDEX_MCP, PINKY_MCP = 0, 3, 4, 5, 17
FINGER_TIPS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}
FINGER_PIPS = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}

# (thumb, index, middle, ring, pinky) -> global pose
GLOBAL_POSES = {
    (0, 1, 0, 0, 0): "cursor",
    (0, 1, 1, 0, 0): "left_click",
    (0, 1, 1, 1, 0): "right_click",
    (1, 0, 0, 0, 0): "scroll_up",
    (1, 0, 0, 0, 1): "scroll_down",
    (0, 1, 0, 0, 1): "drag",
    (0, 0, 0, 0, 0): "neutral",
    (1, 1, 1, 1, 1): "neutral",
}
# Context gestures (profile-dependent actions live in config.profiles)
CONTEXT_POSES = {
    (0, 1, 1, 1, 1): "C1",  # four fingers
    (1, 1, 0, 0, 0): "C2",  # L shape
    (0, 0, 0, 0, 1): "C3",  # little finger only
    (0, 0, 1, 1, 1): "C4",  # middle + ring + little
}
# Middle+ring only (0,0,1,1,0) is a retired pose and deliberately unassigned.


def _d(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def finger_states(lm) -> tuple[int, int, int, int, int]:
    """lm: sequence of 21 (x, y) or (x, y, z) points in image coordinates (y grows down).
    Assumes an upright hand (fingers pointing up), as in a webcam preview."""
    thumb = 1 if _d(lm[THUMB_TIP], lm[PINKY_MCP]) > _d(lm[THUMB_IP], lm[PINKY_MCP]) * 1.15 else 0
    states = [thumb]
    for name in ("index", "middle", "ring", "pinky"):
        tip, pip = lm[FINGER_TIPS[name]], lm[FINGER_PIPS[name]]
        states.append(1 if tip[1] < pip[1] - 0.01 else 0)
    return tuple(states)


def classify(lm) -> tuple[str, str | None]:
    """Return (kind, label): ('global', pose) | ('context', 'C1'..'C4') | ('none', None)."""
    s = finger_states(lm)
    if s in GLOBAL_POSES:
        return "global", GLOBAL_POSES[s]
    if s in CONTEXT_POSES:
        return "context", CONTEXT_POSES[s]
    return "none", None


class HandTracker:
    def __init__(self, max_hands: int = 1, det_conf: float = 0.7, track_conf: float = 0.6):
        import mediapipe as mp
        self._mp = mp
        self._hands = mp.solutions.hands.Hands(
            max_num_hands=max_hands, model_complexity=0,
            min_detection_confidence=det_conf, min_tracking_confidence=track_conf)

    def process(self, rgb_frame):
        """Return (landmarks as list[(x, y, z)], raw_result) or (None, None)."""
        res = self._hands.process(rgb_frame)
        if not res.multi_hand_landmarks:
            return None, None
        h = res.multi_hand_landmarks[0]
        return [(p.x, p.y, p.z) for p in h.landmark], h

    def draw(self, bgr_frame, raw):
        self._mp.solutions.drawing_utils.draw_landmarks(
            bgr_frame, raw, self._mp.solutions.hands.HAND_CONNECTIONS)

    def close(self):
        self._hands.close()


class AdaptiveSmoother:
    """Adaptive smoothing for cursor movement only: heavy when slow, light when fast, with a resting deadzone."""
    def __init__(self, min_alpha: float = 0.08, max_alpha: float = 0.65,
                 speed_scale: float = 0.12, deadzone: float = 0.004):
        self.min_alpha, self.max_alpha = min_alpha, max_alpha
        self.speed_scale, self.deadzone = speed_scale, deadzone
        self.pos = None

    def reset(self):
        self.pos = None

    def update(self, x: float, y: float):
        if self.pos is None:
            self.pos = (x, y)
            return self.pos
        speed = _d((x, y), self.pos)
        if speed < self.deadzone:
            return self.pos
        alpha = min(self.max_alpha, self.min_alpha + speed / self.speed_scale * (self.max_alpha - self.min_alpha))
        self.pos = (self.pos[0] + alpha * (x - self.pos[0]), self.pos[1] + alpha * (y - self.pos[1]))
        return self.pos
