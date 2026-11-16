# Installation (Windows 10/11)
1. Install 64-bit Python 3.12 and Tesseract OCR (add to PATH; install kan/hin/tam/tel data if needed).
2. `py -3.12 -m venv .venv` then `.\.venv\Scripts\Activate.ps1`.
3. `python -m pip install -r requirements-dev.txt` (PyAudio may need a prebuilt wheel).
4. `python -m streamlit run main.py`.
5. Optional: `setx GEMINI_API_KEY "<key>"`; install Ollama and `ollama pull llama3.2`.
