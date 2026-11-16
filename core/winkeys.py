"""Windows media-key sender using SendInput (scan code + extended flag), with a pyautogui fallback."""
from __future__ import annotations
import sys, time

MEDIA_VK = {"play_pause": 0xB3, "next_track": 0xB0, "prev_track": 0xB1, "mute": 0xAD}
MEDIA_NAME = {"play_pause": "playpause", "next_track": "nexttrack", "prev_track": "prevtrack", "mute": "volumemute"}


def _send_input_vk(vk: int) -> bool:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    scan = user32.MapVirtualKeyW(vk, 0)

    def one(flags):
        i = INPUT(type=1)
        i.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        return user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT)) == 1

    ok = one(KEYEVENTF_EXTENDEDKEY)
    time.sleep(0.04)
    ok = one(KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP) and ok
    return ok


def send_media(action_id: str, backend=None) -> bool:
    """Send a system media key. Returns True if it was handed to the OS."""
    vk = MEDIA_VK[action_id]
    if sys.platform == "win32":
        try:
            if _send_input_vk(vk):
                return True
        except Exception:
            pass
    if backend is not None:
        backend.press(MEDIA_NAME[action_id])
        return True
    return False
