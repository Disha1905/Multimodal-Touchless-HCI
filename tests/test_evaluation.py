import pytest
from evaluation import metrics as M


def test_confusion_and_per_class():
    pairs = [("a", "a")] * 8 + [("a", "b")] * 2 + [("b", "b")] * 9 + [("b", "a")]
    labels, m = M.confusion_matrix(pairs)
    assert labels == ["a", "b"] and m == [[8, 2], [1, 9]]
    pc = M.per_class(labels, m)
    assert pc["a"]["recall"] == 0.8 and round(pc["a"]["precision"], 3) == round(8 / 9, 3)
    assert M.accuracy(labels, m) == 17 / 20


def test_sus_known_values():
    assert M.sus_score([5, 1] * 5) == 100.0
    assert M.sus_score([3] * 10) == 50.0
    with pytest.raises(ValueError):
        M.sus_score([1, 2, 3])


def test_latency_and_report():
    s = M.latency_summary([100, 200, None, 300])
    assert s["n"] == 3 and s["mean_ms"] == 200
    trials = [{"user": "u1", "true": "cursor", "pred": "cursor", "latency_ms": "120"},
              {"user": "u1", "true": "cursor", "pred": "none", "latency_ms": ""}]
    assert "Overall accuracy: 50.0%" in M.report(trials)
    assert M.false_trigger_rate(100, 2) == 0.02
