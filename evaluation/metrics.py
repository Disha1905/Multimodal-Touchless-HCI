"""Pure evaluation helpers (no camera needed): confusion matrix, per-class P/R/F1, latency, SUS."""
from __future__ import annotations
import csv, statistics
from collections import Counter, defaultdict


def confusion_matrix(pairs, labels=None):
    """pairs: iterable of (true, predicted). Returns (labels, matrix[true][pred])."""
    pairs = list(pairs)
    labels = list(labels) if labels else sorted({a for a, _ in pairs} | {b for _, b in pairs})
    idx = {l: i for i, l in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for t, p in pairs:
        if t in idx and p in idx:
            m[idx[t]][idx[p]] += 1
    return labels, m


def per_class(labels, m):
    out = {}
    for i, l in enumerate(labels):
        tp = m[i][i]
        fn = sum(m[i]) - tp
        fp = sum(m[r][i] for r in range(len(labels))) - tp
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[l] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
    return out


def accuracy(labels, m):
    total = sum(map(sum, m))
    return sum(m[i][i] for i in range(len(labels))) / total if total else 0.0


def latency_summary(ms):
    ms = [x for x in ms if x is not None]
    if not ms:
        return {"n": 0}
    return {"n": len(ms), "mean_ms": statistics.mean(ms), "median_ms": statistics.median(ms),
            "p95_ms": sorted(ms)[min(len(ms) - 1, int(0.95 * len(ms)))],
            "stdev_ms": statistics.pstdev(ms)}


def false_trigger_rate(neutral_frames: int, triggered_frames: int) -> float:
    """Fraction of frames in which an action fired while the user was idle/neutral."""
    return triggered_frames / neutral_frames if neutral_frames else 0.0


def sus_score(responses) -> float:
    """System Usability Scale: 10 answers, each 1-5. Returns 0-100."""
    r = list(responses)
    if len(r) != 10 or any(not 1 <= x <= 5 for x in r):
        raise ValueError("SUS needs 10 answers between 1 and 5")
    return sum((x - 1) if i % 2 == 0 else (5 - x) for i, x in enumerate(r)) * 2.5


def load_trials(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def report(trials) -> str:
    """trials: list of dicts with true, pred, latency_ms (may be empty), user."""
    pairs = [(t["true"], t["pred"]) for t in trials]
    labels, m = confusion_matrix(pairs)
    pc = per_class(labels, m)
    lat = latency_summary([float(t["latency_ms"]) if t.get("latency_ms") not in (None, "", "None") else None
                           for t in trials])
    lines = [f"Trials: {len(trials)}   Overall accuracy: {accuracy(labels, m):.1%}", "",
             "Per-class results:", f"{'gesture':<14}{'prec':>7}{'recall':>8}{'f1':>7}{'n':>5}"]
    for l in labels:
        c = pc[l]
        lines.append(f"{l:<14}{c['precision']:>7.2f}{c['recall']:>8.2f}{c['f1']:>7.2f}{c['support']:>5}")
    lines += ["", "Confusion matrix (rows = true, cols = predicted):",
              " " * 14 + "".join(f"{l[:7]:>8}" for l in labels)]
    for i, l in enumerate(labels):
        lines.append(f"{l:<14}" + "".join(f"{v:>8}" for v in m[i]))
    lines += ["", f"Latency (gesture start -> stable recognition): {lat}"]
    by_user = defaultdict(list)
    for t in trials:
        by_user[t.get("user", "u1")].append(t["true"] == t["pred"])
    if len(by_user) > 1:
        lines += ["", "Accuracy by user:"] + [f"  {u}: {sum(v)/len(v):.1%} ({len(v)} trials)" for u, v in by_user.items()]
    return "\n".join(lines)
