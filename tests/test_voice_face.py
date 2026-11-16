from modules.voice import COMMANDS, match
from modules.face import FaceEvents


def test_sixteen_commands():
    assert len(COMMANDS) == 16


def test_match_exact_and_search():
    assert match("Next slide.") == ("next_slide", None)
    assert match("right click") == ("right_click", None)
    assert match("search Python tutorials") == ("search", "python tutorials")
    assert match("search") == ("search", None)
    assert match("delete everything now") is None      # not allow-listed
    assert match("please click maybe") is None


BASE = dict(ear_left=0.3, ear_right=0.3, mouth_open=0.02, brow=0.10, yaw=0.0)


def calibrated(sens=1.0):
    fe = FaceEvents(sensitivity=sens, calib_s=2.0)
    t = 0.0
    while not fe.calibrated:
        fe.update(dict(BASE), t)
        t += 0.1
        assert t < 5
    return fe, t


def hold(fe, t, secs, step=0.05, **over):
    """Feed the same face for `secs` seconds; return (events, new time)."""
    m = dict(BASE); m.update(over)
    ev = []
    end = t + secs
    while t < end:
        ev += fe.update(dict(m), t)
        t += step
    return ev, t


def test_calibration_takes_about_two_seconds_and_reports_progress():
    fe = FaceEvents(calib_s=2.0)
    fe.update(dict(BASE), 0.0)
    fe.update(dict(BASE), 1.0)
    assert not fe.calibrated and 0.4 < fe.progress < 0.6
    for i in range(12):
        fe.update(dict(BASE), 1.0 + i * 0.1)
    assert fe.calibrated


def test_calibration_restarts_if_eyes_closed():
    fe = FaceEvents(calib_s=1.0)
    for i in range(15):
        fe.update(dict(BASE, ear_left=0.05, ear_right=0.05), i * 0.1)
    assert not fe.calibrated


def test_wink_fires_once_after_hold_and_only_for_correct_side():
    fe, t = calibrated()
    ev, t = hold(fe, t + 1.0, 0.5, ear_left=0.1)     # sustained left wink
    assert ev.count("left_wink") == 1 and "right_wink" not in ev
    fe2, t2 = calibrated()
    ev2, _ = hold(fe2, t2, 0.5, ear_right=0.1)
    assert ev2 == ["right_wink"]


def test_blink_is_detection_only_and_not_a_wink():
    fe, t = calibrated()
    ev, t = hold(fe, t, 0.25, ear_left=0.1, ear_right=0.1)
    ev2, t = hold(fe, t, 0.3)                         # eyes open again
    assert "blink" in ev + ev2
    assert "left_wink" not in ev + ev2 and "right_wink" not in ev + ev2


def test_mouth_open_needs_a_short_hold_so_talking_does_not_trigger():
    fe, t = calibrated()
    ev, t = hold(fe, t, 0.5, mouth_open=0.30)
    assert "mouth_open" not in ev
    ev, t = hold(fe, t + 1.0, 1.2, mouth_open=0.30)
    assert ev.count("mouth_open") == 1


def test_moderately_open_mouth_is_detected():
    fe, t = calibrated()
    ev, _ = hold(fe, t, 1.2, mouth_open=0.11)        # only ~9 % of face width above neutral
    assert "mouth_open" in ev


def test_brief_speech_like_mouth_movement_is_ignored():
    fe, t = calibrated()
    ev = []
    for _ in range(6):                                # open 0.3 s, close 0.3 s, repeatedly
        e1, t = hold(fe, t, 0.3, mouth_open=0.20)
        e2, t = hold(fe, t, 0.3)
        ev += e1 + e2
    assert "mouth_open" not in ev


def test_eyebrow_raise_is_detected():
    fe, t = calibrated()
    ev, t = hold(fe, t, 0.7, brow=0.125)
    assert ev == ["eyebrow"]


def test_there_is_no_smile_event_any_more():
    fe, t = calibrated()
    ev, _ = hold(fe, t, 1.5, brow=0.10)
    assert "smile" not in ev
    from modules import face
    assert "smile" not in face.HOLD_S and "smile" not in face.COOLDOWN_S


def test_mouth_open_survives_small_fluctuations_thanks_to_hysteresis():
    fe, t = calibrated()
    ev = []
    for i in range(30):                                # wobbles between clearly-open and barely-open
        e, t = hold(fe, t, 0.05, mouth_open=0.12 if i % 2 == 0 else 0.07)
        ev += e
    assert ev.count("mouth_open") == 1


def test_mouth_hold_progress_is_reported_for_on_screen_feedback():
    fe, t = calibrated()
    assert fe.hold_progress("mouth_open") == 0.0
    _, t = hold(fe, t, 0.4, mouth_open=0.30)
    assert 0.3 < fe.hold_progress("mouth_open") < 0.8
    _, t = hold(fe, t, 0.2)                            # mouth closed again
    assert fe.hold_progress("mouth_open") == 0.0


def test_turned_head_blocks_events():
    fe, t = calibrated()
    ev, _ = hold(fe, t, 1.0, ear_left=0.1, yaw=0.3)
    assert ev == [] and "Turn" in fe.note


def test_sensitivity_changes_thresholds():
    low, t = calibrated(0.75)
    high, t2 = calibrated(1.25)
    ev_low, _ = hold(low, t, 0.8, brow=0.1155)        # +15.5 % brow raise
    ev_high, _ = hold(high, t2, 0.8, brow=0.1155)
    assert "eyebrow" not in ev_low and "eyebrow" in ev_high


def test_recalibrate_resets():
    fe, _ = calibrated()
    fe.reset()
    assert not fe.calibrated and fe.progress == 0.0


import pytest


@pytest.mark.parametrize("heard,cid", [
    ("click", "click"), ("quick", "click"), ("write click", "right_click"),
    ("new tap", "new_tab"), ("close tap", "close_tab"), ("play", "play_pause"), ("paws", "play_pause"),
    ("next truck", "next_track"), ("previous truck", "prev_track"), ("moot", "mute"),
    ("next light", "next_slide"), ("previous slides", "prev_slide"),
])
def test_common_mishearings_still_match(heard, cid):
    assert match(heard) == (cid, None)


@pytest.mark.parametrize("heard", ["delete everything", "open command prompt", "hello there", "sing a song"])
def test_unrelated_speech_never_matches(heard):
    assert match(heard) is None
