"""Interruptible speech output. English/Latin: Windows SAPI via PowerShell.
Kannada/Hindi/Tamil/Telugu: Edge neural TTS (edge-tts) with Google TTS fallback + pygame-ce playback."""
from __future__ import annotations
import asyncio, os, re, subprocess, tempfile, threading

EDGE_VOICES = {"kan": "kn-IN-SapnaNeural", "hin": "hi-IN-SwaraNeural",
               "tam": "ta-IN-PallaviNeural", "tel": "te-IN-ShrutiNeural"}
GTTS_LANGS = {"kan": "kn", "hin": "hi", "tam": "ta", "tel": "te", "eng": "en"}


def is_latin(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return not letters or sum(ord(c) < 0x250 for c in letters) / len(letters) > 0.9


def _split_tts_chunks(text: str, limit: int = 180) -> list[str]:
    chunks, cur = [], ""
    for part in re.split(r"(\s+)", text.strip()):
        if len(cur) + len(part) > limit and cur.strip():
            chunks.append(cur.strip())
            cur = ""
        cur += part
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


class Speaker:
    def __init__(self):
        self._proc = None
        self._playing = False
        self._gen = 0
        self._lock = threading.Lock()
        self.last_error = ""

    def speak(self, text: str, lang: str = "eng"):
        text = (text or "").strip()
        if not text:
            return
        self.stop()
        with self._lock:
            self._gen += 1
            gen = self._gen
            self.last_error = ""
        threading.Thread(target=self._run, args=(text, lang, gen), daemon=True).start()

    def _run(self, text: str, lang: str, gen: int):
        try:
            if lang in EDGE_VOICES and not is_latin(text):
                try:
                    self._edge(text, EDGE_VOICES[lang], gen)
                    return
                except Exception as edge_err:
                    if gen != self._gen:
                        return
                    try:
                        self._gtts(text, GTTS_LANGS.get(lang, "en"), gen)
                        return
                    except Exception as gtts_err:
                        if gen == self._gen:
                            self.last_error = f"Speech failed ({edge_err}; fallback: {gtts_err})"
            else:
                self._sapi(text, gen)
        except Exception as e:
            if gen == self._gen:
                self.last_error = f"Speech failed: {e}"

    def _sapi(self, text: str, gen: int):
        safe = text.replace("'", "''")
        ps = ("Add-Type -AssemblyName System.Speech; "
              "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.Speak('{safe}')")
        with self._lock:
            if gen != self._gen:
                return
            self._proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", ps])
        self._proc.wait()

    def _play_mp3(self, path: str, gen: int):
        import pygame
        try:
            with self._lock:
                if gen != self._gen:
                    return
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                self._playing = True
            while self._playing and gen == self._gen and pygame.mixer.music.get_busy():
                pygame.time.wait(80)
        finally:
            try:
                pygame.mixer.music.stop()
                if hasattr(pygame.mixer.music, "unload"):
                    pygame.mixer.music.unload()
            except Exception:
                pass
            try:
                os.remove(path)
            except OSError:
                pass

    def _edge(self, text: str, voice: str, gen: int):
        import edge_tts
        path = os.path.join(tempfile.gettempdir(), f"hci_tts_{gen}.mp3")
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(edge_tts.Communicate(text, voice).save(path))
        finally:
            loop.close()
        if gen != self._gen:
            try:
                os.remove(path)
            except OSError:
                pass
            return
        self._play_mp3(path, gen)

    def _gtts(self, text: str, tl: str, gen: int):
        import requests
        for idx, chunk in enumerate(_split_tts_chunks(text, 180)):
            if gen != self._gen:
                return
            r = requests.get(
                "https://translate.google.com/translate_tts",
                params={"ie": "UTF-8", "q": chunk, "tl": tl, "client": "tw-ob"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            r.raise_for_status()
            path = os.path.join(tempfile.gettempdir(), f"hci_gtts_{gen}_{idx}.mp3")
            with open(path, "wb") as f:
                f.write(r.content)
            self._play_mp3(path, gen)

    def stop(self):
        with self._lock:
            self._gen += 1
            self._playing = False
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
            self._proc = None
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                if hasattr(pygame.mixer.music, "unload"):
                    pygame.mixer.music.unload()
        except Exception:
            pass
