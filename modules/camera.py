"""Threaded webcam reader that keeps only the latest frame."""
from __future__ import annotations
import threading, time


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        self.index, self.width, self.height, self.target_fps = index, width, height, fps
        self.cap = None
        self.frame = None
        self.fps = 0.0
        self.frame_id = 0
        self.ok = False
        self._stop = threading.Event()
        self._t = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        import cv2
        self.cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(self.index)
        if not self.cap or not self.cap.isOpened():
            self.ok = False
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
        self.ok = True
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return True

    def _loop(self):
        n, t0 = 0, time.time()
        while not self._stop.is_set():
            ok, f = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            with self._lock:
                self.frame = f
                self.frame_id += 1
            n += 1
            if time.time() - t0 >= 1.0:
                self.fps, n, t0 = n / (time.time() - t0), 0, time.time()

    def read(self):
        with self._lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self._stop.set()
        if self._t:
            self._t.join(timeout=1.5)
        if self.cap:
            self.cap.release()
        self.ok, self.frame = False, None
