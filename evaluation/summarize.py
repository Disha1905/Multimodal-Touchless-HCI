"""Summarise all recorded trials:  python -m evaluation.summarize [--sus 4,2,5,1,4,2,5,2,4,1 ...]"""
import argparse
from evaluation import metrics

ap = argparse.ArgumentParser()
ap.add_argument("--csv", default="evaluation/results/trials.csv")
ap.add_argument("--sus", action="append", default=[],
                help="one participant's 10 SUS answers (1-5), comma-separated; repeat per participant")
a = ap.parse_args()
text = metrics.report(metrics.load_trials(a.csv))
if a.sus:
    scores = [metrics.sus_score(int(x) for x in s.split(",")) for s in a.sus]
    text += f"\n\nSUS scores: {scores}  mean = {sum(scores)/len(scores):.1f} (68 = average usability)"
print(text)
open("evaluation/results/report.txt", "w").write(text)
