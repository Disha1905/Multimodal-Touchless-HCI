"""Keep Windows from dimming/sleeping the display while the camera is running.

A touchless app produces no keyboard/mouse activity of its own, so Windows' idle timer can dim the screen.
SetThreadExecutionState applies to the CALLING thread, so call it from the long-lived camera loop thread."""
from __future__ import annotations
import sys

ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002


def keep_awake(on: bool) -> bool:
    """Ask Windows to keep the display on (on=True) or return to normal power rules (on=False)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        flags = ES_CONTINUOUS | ((ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED) if on else 0)
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except Exception:
        return False
