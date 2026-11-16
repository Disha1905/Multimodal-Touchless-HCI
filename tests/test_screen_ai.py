import pytest
from modules import screen_ai as S


def test_detect_lang_by_script():
    assert S.detect_lang("Hello world") == "eng"
    assert S.detect_lang("ನಮಸ್ಕಾರ ಜಗತ್ತು") == "kan"
    assert S.detect_lang("नमस्ते दुनिया") == "hin"
    assert S.detect_lang("வணக்கம் உலகம்") == "tam"
    assert S.detect_lang("నమస్కారం ప్రపంచం") == "tel"
    assert S.detect_lang("12345 ...") == "eng"


def test_rebuild_text_keeps_lines_paragraphs_and_confidence():
    d = {"text": ["Hello", "world", "", "Second", "para"],
         "block_num": [1, 1, 1, 2, 2], "par_num": [1, 1, 1, 1, 1], "line_num": [1, 1, 1, 1, 1],
         "conf": ["90", "80", "-1", "70", "60"]}
    text, conf = S.rebuild_text(d)
    assert text == "Hello world\n\nSecond para"
    assert conf == pytest.approx(75.0)


def test_script_ok():
    assert S.script_ok("ನಮಸ್ಕಾರ", "kan") and not S.script_ok("hello", "kan")
    assert S.script_ok("hello there", "eng")


def test_preprocess_upscales_small_images():
    from PIL import Image
    out = S.preprocess(Image.new("RGB", (400, 100), "white"))
    assert out.mode == "L" and out.width == 1200


def test_provider_order_and_missing_keys():
    cfg = S.AIConfig(provider="Auto", gemini_key="")
    assert [n for n, _ in S._providers(cfg)] == ["Gemini", "Ollama (local)"]
    assert [n for n, _ in S._providers(S.AIConfig(provider="Ollama"))] == ["Ollama (local)"]
    assert S._gemini("x", cfg) is None


def test_summarise_uses_first_working_provider(monkeypatch):
    monkeypatch.setattr(S, "_gemini", lambda p, c: None)
    monkeypatch.setattr(S, "_ollama", lambda p, c: "short summary")
    assert S.summarise("long text", S.AIConfig()) == ("short summary", "Ollama (local)")


def test_translate_prefers_google_then_validates_script(monkeypatch):
    monkeypatch.setattr(S, "_google_translate", lambda t, l: "ನಮಸ್ಕಾರ")
    assert S.translate("hello", "kan", S.AIConfig()) == ("ನಮಸ್ಕಾರ", "Google Translate")
    monkeypatch.setattr(S, "_google_translate", lambda t, l: "still english")
    monkeypatch.setattr(S, "_gemini", lambda p, c: None)
    monkeypatch.setattr(S, "_ollama", lambda p, c: "ನಮಸ್ಕಾರ")
    assert S.translate("hello", "kan", S.AIConfig())[1] == "Ollama (local)"


def test_find_tesseract_uses_env_override(tmp_path, monkeypatch):
    exe = tmp_path / "tesseract.exe"; exe.write_text("x")
    monkeypatch.setenv("TESSERACT_CMD", str(exe))
    assert S.find_tesseract() == str(exe)
