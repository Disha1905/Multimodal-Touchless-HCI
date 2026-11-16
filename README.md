# Multimodal Touchless Human-Computer Interaction Engine

A Windows-focused Python + Streamlit prototype: hand-gesture control, optional facial events,
profile-aware application shortcuts, continuous voice commands (MAX Voice), and Screen AI
(OCR, summarization, translation, and interruptible speech output).

> Academic prototype. Automated tests cover software logic only. Webcam, microphone, Windows
> focus, desktop input, Tesseract, online AI services, and speech playback require manual testing
> on the target Windows PC.

## Quick Start (Windows 10/11, 64-bit Python 3.12)

```
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m streamlit run main.py

```

* Install **Tesseract OCR** separately (`winget install -e --id UB-Mannheim.TesseractOCR`) and add it to `PATH`. Missing Indic language packs (`kan`, `hin`, `tam`, `tel`) are downloaded automatically to `user_data/tessdata/` when needed.

* Optional: set `GEMINI_API_KEY` for Gemini; run **Ollama** locally for offline fallback (`OLLAMA_MODEL`, default `llama3.2`).

## Hand Gestures

| Pose | Action | 
| ----- | ----- | 
| Index only | Cursor (adaptive smoothing + resting deadzone) | 
| Index + middle | Left click | 
| Index + middle + ring | Right click | 
| Thumb only | Scroll up | 
| Thumb + little | Scroll down | 
| Index + little | Drag / hold (safe release ends drag) | 
| Fist / open palm | Neutral | 

Controls start **paused**; start the camera, check the preview, then press **Enable controls**.

## Context Gestures

| Profile | C1 (four fingers) | C2 (L shape) | C3 (little finger only) | C4 (middle + ring + little) | 
| ----- | ----- | ----- | ----- | ----- | 
| Browser | Next tab | Previous tab | \- | Close tab | 
| Media | Play / pause | Previous track | Next track | Mute / unmute | 
| PowerPoint | Next slide | Previous slide | \- | \- | 
| Coding IDE | Save | Undo | \- | \- | 
| Default | \- | \- | \- | \- | 

## Dashboard

Six tabs: **Interaction modes**, **Screen AI**, **MAX Voice**, **Settings**, **About & limitations**, and **Account settings**.

## Facial Interaction (Optional, Not Authentication)

* Hold a neutral face for \~2 seconds at start to calibrate.

* **Left / right wink:** Left / right click (instant trigger with two-eye blink suppression).

* **Mouth open (held \~0.8 s):** Toggle MAX Voice on/off (with audible beep, progress bar, and on-screen banner).

* **Blink / eyebrow raise:** Detection only (shown on screen, no action).

* Sensitivity is adjustable in **Settings** (`Low`, `Normal`, `High`). See `docs/TROUBLESHOOTING.md`.

## Media Control

Play/pause, next, and previous use system media keys by default; **Settings -> Advanced** offers a window-targeted keyboard-shortcut method for players that ignore media keys.

## MAX Voice

16 allow-listed commands (`click`, `right click`, `scroll up/down`, `save`, `go back`, `refresh`, `new tab`, `close tab`, `search`, `play/pause`, `next/previous track`, `mute`, `next/previous slide`) plus `search <phrase>`, with Indian-English (`en-IN`) recognition, phonetic aliases, and push-to-talk. Uses Google's online speech recognizer. Nothing is ever executed as a shell command.

## Screen AI

Selected-window capture (`PrintWindow`) -> Tesseract OCR (`eng`, `kan`, `hin`, `tam`, `tel`) -> summarize (Gemini, then local Ollama) or translate (Google Translate, then Gemini, then local Ollama) -> interruptible speech output (Windows SAPI for Latin text; Edge neural TTS with Google TTS fallback for Indic languages).

## Account Access

Username (3-32 letters/digits) + PIN (6-12 digits), salted PBKDF2-HMAC-SHA256 (310k / 180k iterations), 5 failed logins -> 60 s lockout, separate 300 s recovery lockout. Stored in `user_data/access.json` (git-ignored; never publish it).

## Evaluation Methodology & Accuracy

### How Evaluation Is Performed

1. **Hand Gestures (`evaluation/evaluate_gestures.py` + `evaluation/summarize.py`):**

   * Shuffles all 11 target gestures (`cursor`, `left_click`, `right_click`, `scroll_up`, `scroll_down`, `drag`, `neutral`, `C1`–`C4`) across `--trials` repetitions.

   * Each trial gives a **2.5 s `GET READY`** countdown followed by a **1.5 s `HOLD`** capture window, requiring **3 consecutive matching frames (`STABLE_FRAMES = 3`)** to count as a stable prediction.

   * Logs true label, predicted label (most frequent stable label), recognition latency (`ms`), and FPS to `evaluation/results/trials.csv`, then computes overall accuracy, per-class precision/recall/F1, confusion matrix, latency percentiles (`mean`, `median`, `p95`), and optional **SUS usability scores** (`--sus`).

2. **MAX Voice (`evaluation/evaluate_voice.py`):**

   * Calibrates ambient microphone noise for 1 s, shuffles all 16 allow-listed commands across `--trials` repetitions, captures each spoken command via `SpeechRecognition`, and evaluates `modules.voice.match()`.

   * Logs recognized text, predicted command, and end-to-end capture + recognition latency (`ms`) to `evaluation/results/voice_trials.csv` and reports overall accuracy, per-command F1, and confusion matrix.

3. **Screen AI (`evaluation/evaluate_screen_ai.py`):**

   * Renders properly shaped ground-truth text samples for all 5 supported languages (`eng`, `hin`, `kan`, `tam`, `tel`) using Windows native `TextRenderer` (`Nirmala UI`), runs `ocr_auto()` and `translate()`, and computes **OCR character accuracy** (`SequenceMatcher`), **mean Tesseract confidence (%)**, **translation script validation** (`script_ok`), and latency (`ms`), saving results to `evaluation/results/screen_ai_trials.csv`.

### Commands

```
# Hand gestures (auto-clears previous trials.csv)
python -m evaluation.evaluate_gestures --user u1 --trials 3 --light normal
python -m evaluation.summarize

# MAX Voice (auto-clears previous voice_trials.csv)
python -m evaluation.evaluate_voice --user u1 --trials 2 --env quiet

# Screen AI OCR & Translation (auto-clears previous screen_ai_trials.csv)
python -m evaluation.evaluate_screen_ai

```

### Recorded Accuracy & Benchmark Summary

* **Hand Gestures (`evaluation/results/trials.csv`):**

  * **81.8% overall accuracy** across 33 trials (3 trials × 11 gestures, normal lighting; 151.9 ms mean / 117.0 ms median latency).

  * **86.4% accuracy** on the 22-trial run (143.5 ms mean / 133.0 ms median latency), with 1.00 F1 on `C1`, `C2`, `cursor`, `left_click`, `neutral`, and `right_click`.

* **MAX Voice (`evaluation/results/voice_trials.csv`):**

  * **75.0% command recognition accuracy** across 32 trials (16 commands × 2 trials, quiet environment; 3,196.5 ms median end-to-end capture + recognition latency), with 1.00 F1 on `click`, `close_tab`, `mute`, `new_tab`, `refresh`, `right_click`, `save`, `scroll_down`, `scroll_up`, and `search`.

* **Screen AI (`evaluation/results/screen_ai_trials.csv`):**

  * **95.0% average OCR character accuracy** across 5 languages and **100% translation script validation** (via local Ollama):

    * English (`eng`): **100.0%** OCR accuracy (95.7% confidence, 1,134 ms)

    * Hindi (`hin`): **98.4%** OCR accuracy (93.1% confidence, 243 ms) | Translation OK

    * Kannada (`kan`): **95.8%** OCR accuracy (89.4% confidence, 210 ms) | Translation OK

    * Tamil (`tam`): **85.0%** OCR accuracy (90.5% confidence, 244 ms) | Translation OK

    * Telugu (`tel`): **95.9%** OCR accuracy (70.0% confidence, 288 ms) | Translation OK

## Tests

```
python -m pytest -q tests
python -m compileall -q main.py core modules security config tests

```

## Structure

```
hci_engine/
├── main.py            Streamlit dashboard
├── core/              controller, action dispatch, context switching, event policy, alerts, power
├── config/            app-family matching and gesture profiles
├── modules/           hand/face analysis, camera, voice, OCR/AI, speech, performance
├── security/          local username/PIN store
├── evaluation/        gesture, voice, and Screen AI evaluation scripts + CSV results
├── tests/             automated unit tests (mocked integrations)
└── docs/              installation, evaluation plan, testing, privacy, troubleshooting

```

## Limitations

Window targeting relies on titles/process names; shortcuts vary by application; thresholds are heuristic and depend on camera, lighting, and user; online services are required for speech recognition, Google Translate, Gemini, and Indic TTS.