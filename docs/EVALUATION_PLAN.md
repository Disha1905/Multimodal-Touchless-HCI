# Evaluation plan (fits in ~4 hours)

## 1. Gesture accuracy + latency (about 1.5 h)
Per participant (aim for 3+ people) and lighting condition (normal / dim):
```
python -m evaluation.evaluate_gestures --user u1 --trials 20 --light normal
python -m evaluation.evaluate_gestures --user u1 --trials 10 --light dim
```
Each run shows 11 gestures x trials in random order and appends to `evaluation/results/trials.csv`.
Then:  `python -m evaluation.summarize`  -> overall accuracy, per-gesture precision/recall/F1,
confusion matrix, latency (mean/median/p95), accuracy by user. 

## 2. Usability (about 1 h)
Have each participant complete: move cursor to 5 targets, click one, scroll a page, change slide.
Time it with a stopwatch; repeat with a mouse for comparison. Then give them the 10-question SUS form
(odd items positive, even negative; 1-5):
```
python -m evaluation.summarize --sus 4,2,5,1,4,2,5,2,4,1 --sus 5,1,4,2,5,1,4,1,5,2
```
SUS 68 = average; above 80 = excellent.

## 3. Reliability notes (about 1 h)
- Voice: say each of the 16 commands 10 times in quiet and noisy rooms; log hit rate.
- Facial: count false triggers during 2 minutes of normal talking (mouth-open now needs ~1 s hold).
- Performance: note webcam FPS, processing FPS, CPU/memory from the dashboard (hand only vs hand+face).

## Known threats to validity
Few participants, one camera, one room, heuristic thresholds, online services.
