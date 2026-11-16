"""Application families, matching keywords and context-gesture profiles."""

# Distinctive title keywords take priority over process-name matching.
TITLE_KEYWORDS = {
    "media": ["jiosaavn", "spotify", "youtube", "vlc", "netflix", "prime video", "soundcloud"],
    "presentation": ["powerpoint", ".pptx", "slide show"],
    "coding": ["visual studio code", "pycharm", "intellij", "sublime", "notepad++"],
}
PROCESS_NAMES = {
    "browser": ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"],
    "media": ["vlc.exe", "spotify.exe", "wmplayer.exe", "music.ui.exe"],
    "presentation": ["powerpnt.exe"],
    "coding": ["code.exe", "pycharm64.exe", "idea64.exe", "sublime_text.exe"],
}

PROFILE_NAMES = ["Browser", "Media", "PowerPoint", "Coding IDE", "Default"]
FAMILY_TO_PROFILE = {
    "browser": "Browser", "media": "Media", "presentation": "PowerPoint",
    "coding": "Coding IDE", "default": "Default",
}

# Context gestures: C1 four fingers, C2 L shape, C3 little finger only, C4 middle+ring+little.
CONTEXT_GESTURES = {
    "Browser":    {"C1": "next_tab",   "C2": "prev_tab",   "C3": None,         "C4": "close_tab"},
    "Media":      {"C1": "play_pause", "C2": "prev_track", "C3": "next_track", "C4": "mute"},
    "PowerPoint": {"C1": "next_slide", "C2": "prev_slide", "C3": None,         "C4": None},
    "Coding IDE": {"C1": "save",       "C2": "undo",       "C3": None,         "C4": None},
    "Default":    {"C1": None,         "C2": None,         "C3": None,         "C4": None},
}

# Keyboard shortcuts per action (pyautogui key names).
SHORTCUTS = {
    "next_tab": ["ctrl", "tab"],
    "prev_tab": ["ctrl", "pageup"],
    "close_tab": ["ctrl", "w"],
    "new_tab": ["ctrl", "t"],
    "go_back": ["alt", "left"],
    "refresh": ["f5"],
    "focus_address": ["ctrl", "l"],
    "play_pause": ["playpause"],      # global media key: works whatever has focus
    "space": ["space"],                # plain Space (used by the smile event)
    "next_track": ["nexttrack"],
    "prev_track": ["prevtrack"],
    "mute": ["volumemute"],
    "next_slide": ["right"],
    "prev_slide": ["left"],
    "save": ["ctrl", "s"],
    "undo": ["ctrl", "z"],
}
