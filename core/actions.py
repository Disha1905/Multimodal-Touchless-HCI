"""Dispatches abstract actions to desktop input. Blocks input while paused."""
from __future__ import annotations
import time
from collections import deque
from config.profiles import SHORTCUTS
from core import winkeys

MEDIA_ACTIONS = set(winkeys.MEDIA_VK)
DEFAULT_WINDOW_KEYS = {"play_pause": "space", "next_track": "ctrl+right", "prev_track": "ctrl+left", "mute": ""}


class ActionDispatcher:
    def __init__(self, backend=None):
        if backend is None:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0
            backend = pyautogui
        self.b = backend
        self.dragging = False
        self.enabled = False                  # mirrored from EventPolicy by the controller
        self.log: deque = deque(maxlen=8)     # recent discrete actions for the dashboard
        self.prepare = None                   # called before keyboard shortcuts (focus the right window)
        self.focus_target = None              # focus the selected/last external window
        self.media_method = "keys"            # "keys" = system media keys, "window" = shortcuts in target window
        self.window_keys = dict(DEFAULT_WINDOW_KEYS)
        self.vk_sender = lambda action_id: winkeys.send_media(action_id, self.b)

    def note(self, text: str):
        self.log.append((time.strftime("%H:%M:%S"), text))

    def screen_size(self):
        return tuple(self.b.size())

    def move(self, x: int, y: int):
        if self.enabled:
            self.b.moveTo(x, y)

    def click(self, button: str = "left"):
        if self.enabled:
            self.b.click(button=button)
            self.note(f"{button} click")

    def scroll(self, amount: int):
        if self.enabled:
            self.b.scroll(amount)
            self.note("scroll up" if amount > 0 else "scroll down")

    def start_drag(self):
        if self.enabled and not self.dragging:
            self.b.mouseDown()
            self.dragging = True
            self.note("drag start")

    def release_drag(self):
        """Safe release: always ends a drag, even if controls were just paused."""
        if self.dragging:
            self.b.mouseUp()
            self.dragging = False
            self.note("drag release")

    def _press_combo(self, combo: str):
        parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
        if len(parts) > 1:
            self.b.hotkey(*parts)
        elif parts:
            self.b.press(parts[0])

    def _media(self, action_id: str, source) -> bool:
        combo = self.window_keys.get(action_id, "") if self.media_method == "window" else ""
        if combo:
            if self.focus_target:
                self.focus_target()
            self._press_combo(combo)
            how = f"keys: {combo}"
        else:
            self.vk_sender(action_id)
            how = "media key"
        self.note(f"{action_id} [{how}]" + (f"  ({source})" if source else ""))
        return True

    def shortcut(self, action_id, source: str | None = None) -> bool:
        if not self.enabled or not action_id:
            return False
        if action_id in MEDIA_ACTIONS:
            return self._media(action_id, source)
        if action_id not in SHORTCUTS:
            return False
        if self.prepare:
            self.prepare()
        keys = SHORTCUTS[action_id]
        if len(keys) > 1:
            self.b.hotkey(*keys)
        else:
            self.b.press(keys[0])
        self.note(f"{action_id}" + (f"  ({source})" if source else ""))
        return True
