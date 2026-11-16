"""Foreground-window detection, window listing/focus and application-family classification."""
from __future__ import annotations
from config.profiles import TITLE_KEYWORDS, PROCESS_NAMES, FAMILY_TO_PROFILE

OWN_HINT = "multimodal touchless hci"   # title of the dashboard's browser tab


def is_own_window(title: str) -> bool:
    return OWN_HINT in (title or "").lower()


def classify(title: str, process: str) -> str:
    """Return the app family. Title keywords win over process names."""
    t, p = (title or "").lower(), (process or "").lower()
    for family, words in TITLE_KEYWORDS.items():
        if any(w in t for w in words):
            return family
    for family, names in PROCESS_NAMES.items():
        if p in names:
            return family
    return "default"


def profile_for(title: str, process: str) -> str:
    return FAMILY_TO_PROFILE[classify(title, process)]


def _process_name(hwnd) -> str:
    try:
        import win32process, psutil
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name()
    except Exception:
        return ""


def foreground_info() -> tuple[int, str, str]:
    """(hwnd, title, process_name) of the foreground window; (0, '', '') off-Windows."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        return hwnd, win32gui.GetWindowText(hwnd), _process_name(hwnd)
    except Exception:
        return 0, "", ""


def foreground_window() -> tuple[str, str]:
    _, t, p = foreground_info()
    return t, p


def _cloaked(hwnd) -> bool:
    try:
        import ctypes
        v = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(v), ctypes.sizeof(v))
        return bool(v.value)
    except Exception:
        return False


def list_windows(include_own: bool = False) -> list[dict]:
    """Visible, titled, non-tool top-level windows (top of Z-order first), as dicts."""
    out: list[dict] = []
    try:
        import win32gui, win32con

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd).strip()
            if not title or title == "Program Manager" or _cloaked(hwnd):
                return
            if win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOOLWINDOW:
                return
            if not include_own and is_own_window(title):
                return
            out.append({"hwnd": hwnd, "title": title, "process": _process_name(hwnd)})
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return out


def focus_window(hwnd: int) -> bool:
    """Bring a window to the front. Windows blocks background focus changes, so retry with an Alt tap."""
    try:
        import win32gui, win32con, win32api
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        if win32gui.GetForegroundWindow() != hwnd:
            win32api.keybd_event(0x12, 0, 0, 0)
            win32api.keybd_event(0x12, 0, 2, 0)
            win32gui.SetForegroundWindow(hwnd)
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


FRIENDLY_APPS = {
    "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "brave.exe": "Brave",
    "opera.exe": "Opera", "code.exe": "VS Code", "pycharm64.exe": "PyCharm", "powerpnt.exe": "PowerPoint",
    "winword.exe": "Word", "excel.exe": "Excel", "vlc.exe": "VLC", "spotify.exe": "Spotify",
    "notepad.exe": "Notepad", "explorer.exe": "File Explorer", "wmplayer.exe": "Media Player",
    "applicationframehost.exe": "", "teams.exe": "Teams", "whatsapp.exe": "WhatsApp",
}


def friendly_app(process: str) -> str:
    p = (process or "").lower()
    return FRIENDLY_APPS.get(p, (process or "").removesuffix(".exe"))


def window_label(w: dict, maxlen: int = 64) -> str:
    """Readable name for a window: 'Title - App' (Windows-store apps show just the title)."""
    title = w["title"] if len(w["title"]) <= maxlen else w["title"][: maxlen - 1] + "…"
    app = friendly_app(w.get("process", ""))
    return f"{title}  —  {app}" if app and app.lower() not in title.lower() else title
