import pytest
from modules.hand import classify, AdaptiveSmoother
from tests.helpers import hand

GLOBAL = [
    (dict(index=1), "cursor"),
    (dict(index=1, middle=1), "left_click"),
    (dict(index=1, middle=1, ring=1), "right_click"),
    (dict(thumb=1), "scroll_up"),
    (dict(thumb=1, pinky=1), "scroll_down"),
    (dict(index=1, pinky=1), "drag"),
    (dict(), "neutral"),
    (dict(thumb=1, index=1, middle=1, ring=1, pinky=1), "neutral"),
]
CONTEXT = [
    (dict(index=1, middle=1, ring=1, pinky=1), "C1"),
    (dict(thumb=1, index=1), "C2"),
    (dict(pinky=1), "C3"),
    (dict(middle=1, ring=1, pinky=1), "C4"),
]


@pytest.mark.parametrize("kw,label", GLOBAL)
def test_global_poses(kw, label):
    assert classify(hand(**kw)) == ("global", label)


@pytest.mark.parametrize("kw,label", CONTEXT)
def test_context_poses(kw, label):
    assert classify(hand(**kw)) == ("context", label)


def test_retired_middle_ring_pose_unassigned():
    assert classify(hand(middle=1, ring=1)) == ("none", None)


def test_smoother_heavier_when_slow():
    s = AdaptiveSmoother()
    s.update(0.5, 0.5)
    slow = s.update(0.51, 0.5)[0] - 0.5
    s.reset(); s.update(0.5, 0.5)
    fast = s.update(0.9, 0.5)[0] - 0.5
    assert slow / 0.01 < fast / 0.4


def test_old_thumb_middle_pose_is_no_longer_a_gesture():
    assert classify(hand(thumb=1, middle=1)) == ("none", None)


def test_little_finger_only_is_not_confused_with_neighbouring_poses():
    assert classify(hand(pinky=1)) == ("context", "C3")
    assert classify(hand(thumb=1, pinky=1)) == ("global", "scroll_down")   # thumb out: different pose
    assert classify(hand(index=1, pinky=1)) == ("global", "drag")
