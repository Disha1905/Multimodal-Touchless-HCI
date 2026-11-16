"""System-wide performance readings (not per-process). Sampled in the background so the UI never blocks."""
import threading
import time
import psutil

_state = {"cpu": 0.0, "mem": 0.0}
_started = False
_lock = threading.Lock()


class FpsMeter:
    def __init__(self):
        self.n, self.t0, self.fps = 0, time.time(), 0.0

    def tick(self):
        self.n += 1
        dt = time.time() - self.t0
        if dt >= 1.0:
            self.fps, self.n, self.t0 = self.n / dt, 0, time.time()


def _sampler():
    while True:
        _state["cpu"] = psutil.cpu_percent(interval=1.0)
        _state["mem"] = psutil.virtual_memory().percent


def system_stats() -> dict:
    global _started
    with _lock:
        if not _started:
            _started = True
            threading.Thread(target=_sampler, daemon=True).start()
    return {"cpu_percent": _state["cpu"], "memory_percent": _state["mem"] or psutil.virtual_memory().percent}
