import base64, csv, os, subprocess, tempfile, time
from difflib import SequenceMatcher
from PIL import Image
from modules import screen_ai as S

SAMPLES = [
    ("eng", "Touchless human computer interaction uses hand gestures and voice."),
    ("hin", "\u0938\u094d\u092a\u0930\u094d\u0936\u0930\u0939\u093f\u0924 \u092e\u093e\u0928\u0935 \u0915\u0902\u092a\u094d\u092f\u0942\u091f\u0930 \u0938\u0902\u0935\u093e\u0926 \u0939\u093e\u0925 \u0915\u0947 \u0907\u0936\u093e\u0930\u094b\u0902 \u0915\u093e \u0909\u092a\u092f\u094b\u0917 \u0915\u0930\u0924\u093e \u0939\u0948\u0964"),
    ("kan", "\u0cb8\u0ccd\u0caa\u0cb0\u0ccd\u0cb6\u0cb0\u0cb9\u0cbf\u0ca4 \u0cae\u0cbe\u0ca8\u0cb5 \u0c95\u0c82\u0caa\u0ccd\u0caf\u0cc2\u0c9f\u0cb0\u0ccd \u0cb8\u0c82\u0cb5\u0cb9\u0ca8\u0cb5\u0cc1 \u0c95\u0cc8 \u0cb8\u0ca8\u0ccd\u0ca8\u0cc6\u0c97\u0cb3\u0ca8\u0ccd\u0ca8\u0cc1 \u0cac\u0cb3\u0cb8\u0cc1\u0ca4\u0ccd\u0ca4\u0ca6\u0cc6."),
    ("tam", "\u0ba4\u0bca\u0b9f\u0bc1\u0ba4\u0bb2\u0bcd \u0b87\u0bb2\u0bcd\u0bb2\u0bbe\u0ba4 \u0bae\u0ba9\u0bbf\u0ba4 \u0b95\u0ba3\u0bbf\u0ba9\u0bbf \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0baa\u0bc1 \u0b95\u0bc8 \u0b9a\u0bc8\u0b95\u0bc8\u0b95\u0bb3\u0bc8 \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."),
    ("tel", "\u0c38\u0c4d\u0c2a\u0c30\u0c4d\u0c36\u0c30\u0c39\u0c3f\u0c24 \u0c2e\u0c3e\u0c28\u0c35 \u0c15\u0c02\u0c2a\u0c4d\u0c2f\u0c42\u0c1f\u0c30\u0c4d \u0c38\u0c02\u0c2d\u0c3e\u0c37\u0c23 \u0c1a\u0c47\u0c24\u0c3f \u0c38\u0c02\u0c1c\u0c4d\u0c1e\u0c32\u0c28\u0c41 \u0c09\u0c2a\u0c2f\u0c4b\u0c17\u0c3f\u0c38\u0c4d\u0c24\u0c41\u0c02\u0c26\u0c3f."),
]

def render_native(text: str, tag: str) -> Image.Image:
    out_png = os.path.join(tempfile.gettempdir(), f"hci_eval_{tag}.png")
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    ps = (
        "Add-Type -AssemblyName System.Drawing,System.Windows.Forms; "
        f"$t = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}')); "
        "$bmp = New-Object System.Drawing.Bitmap 1400, 220; "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.Clear([System.Drawing.Color]::White); "
        "$f = New-Object System.Drawing.Font('Nirmala UI', 28); "
        "$rect = New-Object System.Drawing.Rectangle 30, 70, 1340, 120; "
        "[System.Windows.Forms.TextRenderer]::DrawText($g, $t, $f, $rect, [System.Drawing.Color]::Black); "
        f"$bmp.Save('{out_png}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "$g.Dispose(); $bmp.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    return Image.open(out_png).convert("RGB")

def main():
    os.makedirs("evaluation/results", exist_ok=True)
    cfg = S.AIConfig.from_env()
    out_path = "evaluation/results/screen_ai_trials.csv"
    rows = []
    for lang, truth in SAMPLES:
        img = render_native(truth, lang)
        t0 = time.time()
        extracted, conf, _, _ = S.ocr_auto(img, lang)
        ocr_ms = (time.time() - t0) * 1000
        char_acc = SequenceMatcher(None, truth, extracted.strip()).ratio() * 100
        t1 = time.time()
        trans, prov = S.translate("Touchless computer control is working.", lang, cfg) if lang != "eng" else ("Touchless computer control is working.", "n/a")
        tr_ms = (time.time() - t1) * 1000
        tr_ok = S.script_ok(trans, lang)
        rows.append({
            "lang": lang, "ocr_char_acc": f"{char_acc:.1f}%",
            "tess_conf": f"{conf:.1f}%", "ocr_ms": f"{ocr_ms:.0f}",
            "trans_ok": tr_ok, "trans_prov": prov, "trans_ms": f"{tr_ms:.0f}"
        })
        print(f"{lang}: OCR char_acc={char_acc:.1f}% conf={conf:.1f}% ({ocr_ms:.0f} ms) | Trans OK={tr_ok} via {prov} ({tr_ms:.0f} ms)")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\nSaved to {out_path}")

if __name__ == "__main__":
    main()
