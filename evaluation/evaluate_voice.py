import argparse, csv, os, random, time
import speech_recognition as sr
from modules.voice import COMMANDS, LANGUAGE, match
from evaluation import metrics

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="u1")
    ap.add_argument("--trials", type=int, default=2, help="trials per command")
    ap.add_argument("--env", default="quiet")
    a = ap.parse_args()

    os.makedirs("evaluation/results", exist_ok=True)
    out_path = "evaluation/results/voice_trials.csv"
    f = open(out_path, "w", newline="", encoding="utf-8")
    new = True
    w = csv.DictWriter(f, fieldnames=["user", "env", "true", "pred", "match_pct", "overall_accuracy_pct", "heard", "latency_ms"])
    if new:
        w.writeheader()

    rec, mic = sr.Recognizer(), sr.Microphone()
    with mic as src:
        print("Calibrating mic noise (1 s)...")
        rec.adjust_for_ambient_noise(src, duration=1.0)

    order = list(COMMANDS.keys()) * a.trials
    random.shuffle(order)
    rows = []
    for i, cid in enumerate(order, 1):
        phrase = COMMANDS[cid][2] if cid == 'play_pause' else COMMANDS[cid][-1] if cid in ('click', 'save', 'play_pause') else COMMANDS[cid][0]
        input(f"[{i}/{len(order)}] Press Enter, then say: '{phrase}'")
        t0 = time.time()
        try:
            with mic as src:
                audio = rec.listen(src, timeout=5, phrase_time_limit=4)
            text = rec.recognize_google(audio, language=LANGUAGE)
            res = match(text)
            pred = res[0] if res else "none"
        except Exception as e:
            text, pred = f"({type(e).__name__})", "none"
        lat = (time.time() - t0) * 1000
        print(f"  Heard: '{text}' -> pred={pred} ({lat:.0f} ms)")
        row = {"user": a.user, "env": a.env, "true": cid, "pred": pred,
               "match_pct": "100.0%" if cid == pred else "0.0%", "overall_accuracy_pct": "",
               "heard": text, "latency_ms": f"{lat:.0f}"}
        w.writerow(row); f.flush(); rows.append(row)
    f.close()
    if rows:
        pct = f"{sum(r['true'] == r['pred'] for r in rows) / len(rows) * 100:.1f}%"
        for r in rows: r["overall_accuracy_pct"] = pct
        with open(out_path, "w", newline="", encoding="utf-8") as wf:
            dw = csv.DictWriter(wf, fieldnames=list(rows[0].keys()))
            dw.writeheader(); dw.writerows(rows)
    print("\n" + metrics.report(rows))

if __name__ == "__main__":
    main()
