# Privacy and security
- Camera frames are processed locally; nothing is saved.
- MAX Voice sends command audio to Google's recognizer; Screen AI text may go to Google Translate / Gemini.
- Only the selected application window is captured.
- PINs and recovery codes are stored as salted PBKDF2 verifiers; keep `user_data/` private.
- Facial interaction is not authentication.
