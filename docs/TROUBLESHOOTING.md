# Troubleshooting

## Media gestures / voice do nothing
1. Settings -> Advanced (play / next / previous do nothing?) -> press **Play / pause** (controls must be enabled). Watch *Recent actions*.
2. Start music in the browser first. System media keys only reach a player that is playing or recently played.
3. Still nothing, or next/previous ignored by the website: choose **Keyboard shortcuts in the target window**
   and set the keys your player uses (e.g. `space`, `shift+n`, `ctrl+right`). Select the player window in
   MAX Voice -> Target application window (or leave it on Automatic).

## Dashboard too big or too small
Use the browser zoom (Ctrl + minus / Ctrl + plus). The layout is designed to fit one screen at 100 %-110 %.

## Screen AI says Tesseract was not found
`winget install -e --id UB-Mannheim.TesseractOCR`, close and reopen the terminal, restart the app.
Kannada/Hindi/Tamil/Telugu packs download automatically on first use (internet needed).

## Voice commands not recognised
Check *heard* in System state: it shows exactly what the recogniser returned. Speak clearly, reduce
background audio, and keep the microphone close. Recognition language can be changed with the
`HCI_VOICE_LANG` environment variable (default `en-IN`).

## Facial events are too sensitive / not sensitive enough
Settings -> Facial interaction -> Sensitivity, then press **Recalibrate face** with a relaxed face.
Calibrate in the lighting you will use; look straight at the camera.

## Low FPS
Close other programs (watch memory use), lower the camera FPS target in Settings, turn off facial analysis.
