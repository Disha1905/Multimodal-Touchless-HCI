"""Event policy: stability filtering, cooldowns and the paused-by-default gate."""
from __future__ import annotations
import time


class EventPolicy:
    def __init__(self, stable_frames: int = 3, cooldown: float = 0.6, clock=time.monotonic):
        self.stable_frames = stable_frames
        self.cooldown = cooldown
        self.clock = clock
        self.controls_enabled = False  # computer control starts PAUSED
        self._candidate = None
        self._count = 0
        self._last_fire: dict[str, float] = {}

    def stable(self, label):
        """Return label only once it has persisted for `stable_frames` frames."""
        if label == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = label, 1
        return label if self._count >= self.stable_frames else None

    def allow(self, event: str) -> bool:
        now = self.clock()
        if now - self._last_fire.get(event, -1e9) < self.cooldown:
            return False
        self._last_fire[event] = now
        return True
