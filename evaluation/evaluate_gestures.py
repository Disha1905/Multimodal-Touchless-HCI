"""Live gesture evaluation. Run on the Windows PC with a webcam:

    python -m evaluation.evaluate_gestures --user u1 --trials 20 --light normal

For each trial you are asked to make a gesture; the script records what the system recognised
(most frequent stable label in the window) and the time to first correct recognition.
Results append to evaluation/results/trials.csv; a report is printed and saved at the end.
Tip: run once per participant / lighting condition, then `python -m evaluation.summarize`."""
from __future__ import annotations
import argparse, csv, os, random, time
from collections import Counter

from modules import hand as H
from evaluation import metrics

TARGETS = ["cursor", "left_click", "right_click", "scroll_up", "scroll_down", "drag", "neutral",
           "C1", "C2", "C3", "C4"]
STABLE_FRAMES = 3
READY_S, WINDOW_S = 2.5, 1.5


def main():
    import cv2
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="u1")
    ap.add_argument("--trials", type=int, default=20, help="trials per gesture")
    ap.add_argument("--light", default="normal")
    ap.add_argument("--camera", type=int, default=0)
    a = ap.parse_args()

    os.makedirs("evaluation/results", exist_ok=True)
    out_path = "evaluation/results/trials.csv"
    f = open(out_path, "w", newline="")
    new = True
    w = csv.DictWriter(f, fieldnames=["user", "light", "true", "pred", "match_pct", "overall_accuracy_pct", "latency_ms", "fps"])
    if new:
        w.writeheader()

    cap = cv2.VideoCapture(a.camera)
    tracker = H.HandTracker()
    order = TARGETS * a.trials
    random.shuffle(order)
    names = {"C1": "four fingers", "C2": "L shape", "C3": "little finger only", "C4": "middle+ring+little"}
    results = []
    quit_now = False
    for n, target in enumerate(order, 1):
        t_ready = time.time()
        while time.time() - t_ready < READY_S:                 # get-ready phase
            ok, fr = cap.read()
            if not ok:
                continue
            fr = cv2.flip(fr, 1)
            cv2.putText(fr, f"[{n}/{len(order)}] GET READY: {target} {names.get(target,'')}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
            cv2.imshow("Gesture evaluation (q to quit)", fr)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                quit_now = True
                break
        if quit_now:
            break
        t0, frames, labels, first_ok, last, run = time.time(), 0, [], None, None, 0
        while time.time() - t0 < WINDOW_S:
            ok, fr = cap.read()
            if not ok:
                continue
            fr = cv2.flip(fr, 1)
            lm, raw = tracker.process(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
            lab = None
            if lm is not None:
                kind, lab = H.classify(lm)
                lab = lab if kind != "none" else None
            frames += 1
            run = run + 1 if lab == last else 1
            last = lab
            if run >= STABLE_FRAMES and lab is not None:
                labels.append(lab)
                if lab == target and first_ok is None:
                    first_ok = (time.time() - t0) * 1000
            cv2.putText(fr, f"HOLD: {target}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            cv2.imshow("Gesture evaluation (q to quit)", fr)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                quit_now = True
                break
        if quit_now:
            break
        pred = Counter(labels).most_common(1)[0][0] if labels else "none"
        row = {"user": a.user, "light": a.light, "true": target, "pred": pred,
               "match_pct": "100.0%" if target == pred else "0.0%", "overall_accuracy_pct": "",
               "latency_ms": f"{first_ok:.0f}" if first_ok is not None else "", "fps": f"{frames / WINDOW_S:.1f}"}
        w.writerow(row); f.flush(); results.append(row)
    cap.release(); cv2.destroyAllWindows(); tracker.close(); f.close()
    if results:
        pct = f"{sum(r['true'] == r['pred'] for r in results) / len(results) * 100:.1f}%"
        for r in results: r["overall_accuracy_pct"] = pct
        with open(out_path, "w", newline="") as wf:
            dw = csv.DictWriter(wf, fieldnames=list(results[0].keys()))
            dw.writeheader(); dw.writerows(results)
    print(metrics.report(results))


if __name__ == "__main__":
    main()
