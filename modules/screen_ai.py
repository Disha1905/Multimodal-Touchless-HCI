"""Screen AI: selected-window capture -> Tesseract OCR -> summarise / translate."""
from __future__ import annotations
import os, re, shutil, sys
from dataclasses import dataclass
from pathlib import Path
import requests

LANG_LABELS = {"eng": "English", "kan": "Kannada", "hin": "Hindi", "tam": "Tamil", "tel": "Telugu"}
GOOGLE_CODES = {"eng": "en", "kan": "kn", "hin": "hi", "tam": "ta", "tel": "te"}
SCRIPT_RANGES = {"kan": (0x0C80, 0x0CFF), "hin": (0x0900, 0x097F),
                 "tam": (0x0B80, 0x0BFF), "tel": (0x0C00, 0x0C7F)}
TESSDATA_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata"
import sys
_DATA_ROOT = Path(os.environ.get("LOCALAPPDATA", ".")) / "MultimodalTouchlessHCI" if getattr(sys, "frozen", False) else Path("user_data")
USER_TESSDATA = _DATA_ROOT / "tessdata"
TESS_HELP = ("Tesseract OCR was not found. Install it with:  winget install -e --id UB-Mannheim.TesseractOCR  "
             "then restart the app.")


# ------------------------------------------------------------------ AI provider settings
@dataclass
class AIConfig:
    provider: str = "Auto"            # Auto | Gemini | Ollama
    gemini_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    @classmethod
    def from_env(cls) -> "AIConfig":
        return cls(gemini_key=os.environ.get("GEMINI_API_KEY", ""),
                   gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
                   ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
                   ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.2"))


# ------------------------------------------------------------------ Tesseract discovery / language packs
def find_tesseract() -> str | None:
    cands = [os.environ.get("TESSERACT_CMD"), str(Path(getattr(sys, "_MEIPASS", ".")) / "tesseract" / "tesseract.exe"), shutil.which("tesseract"),
             r"C:\Program Files\Tesseract-OCR\tesseract.exe",
             r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
             os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def configure_tesseract() -> str | None:
    cmd = find_tesseract()
    if cmd:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = cmd
    return cmd


def installed_languages() -> set[str]:
    """Language packs Tesseract itself can see."""
    try:
        import pytesseract
        if not configure_tesseract():
            return set()
        return set(pytesseract.get_languages(config=""))
    except Exception:
        return set()


_ORIG_PREFIX = os.environ.get("TESSDATA_PREFIX")


def _download_pack(lang: str) -> tuple[bool, str]:
    target = USER_TESSDATA / f"{lang}.traineddata"
    if target.exists() and target.stat().st_size > 10_000:
        return True, ""
    try:
        USER_TESSDATA.mkdir(parents=True, exist_ok=True)
        r = requests.get(TESSDATA_URL.format(lang=lang), timeout=90)
        r.raise_for_status()
        target.write_bytes(r.content)
        return True, f"Downloaded the {LANG_LABELS.get(lang, lang)} OCR pack. "
    except Exception as e:
        return False, f"Could not download the {LANG_LABELS.get(lang, lang)} OCR pack ({e}). "


def prepare_languages(langs: list[str]) -> tuple[bool, str, bool]:
    """Make every language in `langs` usable. Returns (ok, message, use_user_dir).
    Tesseract reads one tessdata folder, so if anything is missing from the installed packs, all
    requested packs are kept together in user_data/tessdata."""
    installed = installed_languages()
    if all(l in installed for l in langs):
        return True, "", False
    msg = ""
    for l in langs:
        ok, m = _download_pack(l)
        msg += m
        if not ok:
            return False, msg, False
    return True, msg, True


def ensure_language(lang: str) -> tuple[bool, str, bool]:
    return prepare_languages([lang])


# ------------------------------------------------------------------ capture
def capture_window(hwnd: int):
    """Capture ONLY the selected window's own pixels (works even when other windows cover it).
    Returns (PIL image, method)."""
    import ctypes
    import win32gui, win32ui
    from PIL import Image, ImageGrab
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    if win32gui.IsIconic(hwnd):
        import win32con
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    w, h = max(1, r - l), max(1, b - t)
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc, save = None, None
    try:
        mfc = win32ui.CreateDCFromHandle(hwnd_dc)
        save = mfc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc, w, h)
        save.SelectObject(bmp)
        ok = ctypes.windll.user32.PrintWindow(hwnd, save.GetSafeHdc(), 2)    # 2 = PW_RENDERFULLCONTENT
        info, bits = bmp.GetInfo(), bmp.GetBitmapBits(True)
        img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), bits, "raw", "BGRX", 0, 1)
        win32gui.DeleteObject(bmp.GetHandle())
        lo, hi = img.convert("L").getextrema()
        if ok and hi - lo > 8:                       # not a blank bitmap
            return img, "window pixels"
    finally:
        if save:
            save.DeleteDC()
        if mfc:
            mfc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
    return ImageGrab.grab(bbox=(l, t, r, b), all_screens=True), "screen region (window must be visible)"


# ------------------------------------------------------------------ OCR
def preprocess(image):
    """Grayscale, upscale small captures and stretch contrast: improves Tesseract accuracy."""
    from PIL import ImageOps, Image
    g = image.convert("L")
    if g.width < 1800:
        f = 2 if g.width >= 900 else 3
        g = g.resize((g.width * f, g.height * f), Image.LANCZOS)
    return ImageOps.autocontrast(g)


def rebuild_text(d: dict) -> tuple[str, float]:
    """Rebuild reading-order text and mean confidence from pytesseract image_to_data output."""
    lines: dict[tuple, list[str]] = {}
    confs = []
    for i, w in enumerate(d["text"]):
        if not str(w).strip():
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        lines.setdefault(key, []).append(str(w))
        try:
            c = float(d["conf"][i])
            if c >= 0:
                confs.append(c)
        except (ValueError, TypeError):
            pass
    out, last_par = [], None
    for (blk, par, _ln), words in lines.items():
        if last_par is not None and (blk, par) != last_par:
            out.append("")
        out.append(" ".join(words))
        last_par = (blk, par)
    return "\n".join(out).strip(), (sum(confs) / len(confs) if confs else 0.0)


def ocr(image, lang: str = "eng") -> tuple[str, float, str]:
    """OCR with one language code or several joined by '+'. Returns (text, mean confidence 0-100, message).
    Raises RuntimeError with a helpful message."""
    import pytesseract
    if not configure_tesseract():
        raise RuntimeError(TESS_HELP)
    ok, msg, use_user = prepare_languages(lang.split("+"))
    if not ok:
        raise RuntimeError(msg)
    if use_user:
        os.environ["TESSDATA_PREFIX"] = str(USER_TESSDATA.resolve())
    elif _ORIG_PREFIX is None:
        os.environ.pop("TESSDATA_PREFIX", None)
    else:
        os.environ["TESSDATA_PREFIX"] = _ORIG_PREFIX
    use_dir = use_user or all((USER_TESSDATA / f"{l}.traineddata").exists() for l in lang.split("+"))
    cfg_str = f"--psm 3 --tessdata-dir {USER_TESSDATA.resolve().as_posix()}" if use_dir else "--psm 3"
    d = pytesseract.image_to_data(preprocess(image), lang=lang, config=cfg_str,
                                  output_type=pytesseract.Output.DICT)
    text, conf = rebuild_text(d)
    return text, conf, msg


def ocr_auto(image, forced: str | None = None) -> tuple[str, float, str, str]:
    """Automatic language: fast English pass first; if the result looks weak, retry with all five
    languages together and keep the better one. Returns (text, confidence, message, language used)."""
    if forced and forced != "auto":
        t, c, m = ocr(image, forced)
        return t, c, m, forced
    t1, c1, m1 = ocr(image, "eng")
    if t1.strip() and c1 >= 80 and script_ok(t1, "eng"):
        return t1, c1, m1, "eng"
    combo = "+".join(LANG_LABELS)
    try:
        t2, c2, m2 = ocr(image, combo)
    except RuntimeError:
        return t1, c1, m1, "eng"
    if (t2.strip() and not t1.strip()) or c2 > c1 + 3:
        return t2, c2, m1 + m2, combo
    return t1, c1, m1, "eng"


def to_data_uri(image, max_width: int = 1100) -> str:
    """PNG/JPEG as a base64 data URI so the preview always renders (no media-file expiry)."""
    import base64, io
    img = image.convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, int(img.height * max_width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# ------------------------------------------------------------------ language helpers
def detect_lang(text: str) -> str:
    """Dominant script of `text` as an OCR/TTS language code (Latin -> eng)."""
    counts = {l: 0 for l in SCRIPT_RANGES}
    latin = 0
    for c in text:
        if not c.isalpha():
            continue
        o = ord(c)
        for l, (lo, hi) in SCRIPT_RANGES.items():
            if lo <= o <= hi:
                counts[l] += 1
                break
        else:
            latin += 1
    best = max(counts, key=counts.get)
    return best if counts[best] > latin else "eng"


def script_ok(text: str, lang: str) -> bool:
    """Heuristic check that output is mostly in the target script (cannot prove correctness)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    if lang in SCRIPT_RANGES:
        lo, hi = SCRIPT_RANGES[lang]
        return sum(lo <= ord(c) <= hi for c in letters) / len(letters) > 0.5
    return sum(ord(c) < 0x250 for c in letters) / len(letters) > 0.8


# ------------------------------------------------------------------ providers
def _gemini(prompt: str, cfg: AIConfig) -> str | None:
    if not cfg.gemini_key:
        return None
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.gemini_model}:generateContent",
            headers={"x-goog-api-key": cfg.gemini_key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=40)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None


def _ollama(prompt: str, cfg: AIConfig) -> str | None:
    try:
        r = requests.post(f"{cfg.ollama_host}/api/generate",
                          json={"model": cfg.ollama_model, "prompt": prompt, "stream": False}, timeout=120)
        r.raise_for_status()
        return r.json()["response"].strip()
    except Exception:
        return None


def _providers(cfg: AIConfig):
    order = {"Gemini": [("Gemini", _gemini)], "Ollama": [("Ollama (local)", _ollama)]}
    return order.get(cfg.provider, [("Gemini", _gemini), ("Ollama (local)", _ollama)])


def _chunks(text: str, n: int):
    cur = ""
    for p in re.split(r"(?<=[.!?\n])", text):
        if len(cur) + len(p) > n and cur:
            yield cur
            cur = ""
        cur += p
    if cur:
        yield cur


def _google_translate(text: str, target: str) -> str | None:
    try:
        out = []
        for chunk in _chunks(text, 1500):
            r = requests.get("https://translate.googleapis.com/translate_a/single",
                             params={"client": "gtx", "sl": "auto", "tl": GOOGLE_CODES[target],
                                     "dt": "t", "q": chunk}, timeout=20)
            r.raise_for_status()
            out.append("".join(seg[0] for seg in r.json()[0] if seg[0]))
        return "".join(out).strip() or None
    except Exception:
        return None


def summarise(text: str, cfg: AIConfig | None = None) -> tuple[str, str]:
    """Returns (summary, provider)."""
    cfg = cfg or AIConfig.from_env()
    prompt = "Summarise the following text concisely in the same language:\n\n" + text[:8000]
    for name, fn in _providers(cfg):
        out = fn(prompt, cfg)
        if out:
            return out, name
    return "No AI provider available. Add a Gemini key in AI provider settings, or start Ollama.", "none"


def translate(text: str, target: str, cfg: AIConfig | None = None) -> tuple[str, str]:
    """Returns (translation, provider). Google Translate -> Gemini -> Ollama."""
    cfg = cfg or AIConfig.from_env()
    out = _google_translate(text, target)
    if out and script_ok(out, target):
        return out, "Google Translate"
    prompt = (f"Translate the following text into {LANG_LABELS[target]}. "
              f"Output only the translation.\n\n{text[:8000]}")
    for name, fn in _providers(cfg):
        res = fn(prompt, cfg)
        if res and script_ok(res, target):
            return res, name
    return "Translation unavailable (no provider returned suitable output).", "none"
