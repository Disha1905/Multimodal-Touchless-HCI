"""MAX Voice: continuous listening (user-started, no wake phrase) -> allow-listed commands only.
Speech is never passed to a shell or executed as code."""
from __future__ import annotations
import difflib, os, re, threading, time

LANGUAGE = os.environ.get("HCI_VOICE_LANG", "en-IN")   # recognizer language

# 16 predefined command IDs -> accepted phrases
COMMANDS: dict[str, list[str]] = {
    # Common
    "click": ["click", "left click"],
    "right_click": ["right click"],
    "scroll_up": ["scroll up"],
    "scroll_down": ["scroll down"],
    "save": ["save", "save file"],
    # Browser
    "go_back": ["go back", "back"],
    "refresh": ["refresh", "reload"],
    "new_tab": ["new tab", "open new tab"],
    "close_tab": ["close tab"],
    "search": ["search"],
    # Media
    "play_pause": ["play", "pause", "play pause", "resume"],
    "next_track": ["next track", "next song"],
    "prev_track": ["previous track", "previous song"],
    "mute": ["mute", "unmute"],
    # Presentation
    "next_slide": ["next slide"],
    "prev_slide": ["previous slide"],
}
assert len(COMMANDS) == 16

# Words the recognizer commonly returns instead of the real command (accepted as aliases).
ALIASES: dict[str, list[str]] = {
    "click": ["quick", "clique", "klick", "clicks", "left quick"],
    "right_click": ["write click", "right quick", "white click", "ride click", "right clip", "right clicks"],
    "new_tab": ["new tap", "new top", "nu tab", "new tabs", "open tab", "open a new tab"],
    "close_tab": ["close tap", "close top", "clothes tab", "close the tab", "close tabs"],
    "play_pause": ["paws", "pose", "plays", "played", "paused", "start music", "stop music"],
    "next_track": ["next truck", "next tract", "next tracks", "next track please", "skip song", "skip", "track"],
    "prev_track": ["previous truck", "previous tract", "previous tracks", "last song", "last track", "back track", "vs track"],
    "mute": ["moot", "mutt", "meet", "muted", "mute it"],
    "next_slide": ["next light", "next slides", "next side", "next slight", "forward slide"],
    "prev_slide": ["previous light", "previous slides", "previous side", "back slide", "last slide", "vs slide"],
}

_PHRASES = sorted(
    ((p, cid) for cid in COMMANDS for p in COMMANDS[cid] + ALIASES.get(cid, [])),
    key=lambda x: -len(x[0]))
_PHRASE_TEXT = [p for p, _ in _PHRASES]
_SEARCH_RE = re.compile(r"^search (?:for )?(.+)$")


def match(text: str):
    """Return (command_id, argument|None) or None. Exact phrase match only."""
    t = re.sub(r"[^a-z0-9 ]", "", (text or "").lower()).strip()
    if not t:
        return None
    m = _SEARCH_RE.match(t)
    if m:
        return "search", m.group(1).strip()
    for phrase, cid in _PHRASES:
        if t == phrase:
            return cid, None
    close = difflib.get_close_matches(t, _PHRASE_TEXT, n=1, cutoff=0.84)   # tolerate slight mis-hearing
    if close:
        return dict(_PHRASES)[close[0]], None
    return None


class VoiceListener:
    def __init__(self, on_command, on_status=None, on_heard=None):
        self.on_command, self.on_status = on_command, on_status or (lambda s: None)
        self.on_heard = on_heard or (lambda text, res: None)
        self.active = False
        self.last_heard = ""
        self._stop_fn = None

    def start(self) -> bool:
        if self.active:
            return True
        try:
            import speech_recognition as sr
            self._sr = sr
            self._rec = sr.Recognizer()
            self._mic = sr.Microphone()
            with self._mic as src:
                self._rec.adjust_for_ambient_noise(src, duration=0.5)
            self._stop_fn = self._rec.listen_in_background(self._mic, self._cb, phrase_time_limit=5)
            self.active = True
            self.on_status("Listening")
            return True
        except Exception as e:  # no mic / PyAudio missing
            self.on_status(f"Microphone unavailable: {e}")
            return False

    def _cb(self, rec, audio):
        try:
            text = rec.recognize_google(audio, language=LANGUAGE)  # online: audio is sent to Google
        except Exception:
            return
        self.last_heard = text
        res = match(text)
        self.on_heard(text, res)
        if res:
            self.on_command(*res)

    def listen_once(self, timeout: float = 5, phrase_limit: float = 5):
        """Push-to-talk: capture a single utterance and run it if it is an allow-listed command."""
        try:
            import speech_recognition as sr
            rec, mic = sr.Recognizer(), sr.Microphone()
            self.on_status("Listening (push-to-talk)")
            with mic as src:
                rec.adjust_for_ambient_noise(src, duration=0.3)
                audio = rec.listen(src, timeout=timeout, phrase_time_limit=phrase_limit)
            text = rec.recognize_google(audio, language=LANGUAGE)
        except Exception as e:
            self.on_status(f"No command heard ({type(e).__name__})")
            return
        self.last_heard = text
        res = match(text)
        self.on_heard(text, res)
        self.on_status("Stopped" if not self.active else "Listening")
        if res:
            self.on_command(*res)

    def stop(self):
        if self._stop_fn:
            self._stop_fn(wait_for_stop=False)
            self._stop_fn = None
        self.active = False
        self.on_status("Stopped")

    def toggle(self):
        self.stop() if self.active else self.start()
