import pytest

from wathba.motion import Plan, analyse_trace, interior_angle, measure_keypoints


def samples(angles, step=.5):
    return [{"time": i * step, "angle": a, "confidence": .95 if a is not None else .1} for i, a in enumerate(angles)]


def test_complete_cycles_and_fast_cycle():
    result = analyse_trace(samples([90, 120, 155, 120, 90, 155, 90]), Plan())
    assert result["repetitions"] == 2
    assert [f["kind"] for f in result["flags"]] == ["pace"]
    assert result["flags"][0]["rep"] == 2


def test_uncertain_observations_do_not_complete_cycle():
    result = analyse_trace(samples([90, 155, None, None, 90, 120, 155, 120, 90]), Plan())
    assert result["repetitions"] == 1
    assert any(f["kind"] == "tracking" for f in result["flags"])


def test_missing_interval_resets_cycle():
    trace = [{"time": 0, "angle": 90, "confidence": .9}, {"time": .5, "angle": 155, "confidence": .9}, {"time": 3, "angle": 90, "confidence": .9}]
    assert analyse_trace(trace, Plan())["repetitions"] == 0


def test_low_confidence_is_not_a_valid_angle():
    points = [[0, 0] for _ in range(17)]
    points[12], points[14], points[16] = [0, 0], [1, 0], [1, 1]
    scores = [.9] * 17
    assert measure_keypoints(points, scores, "Right")[0] == pytest.approx(90)
    scores[16] = .1
    assert measure_keypoints(points, scores, "Right")[0] is None


def test_no_reliable_tracking_has_actionable_error():
    with pytest.raises(ValueError, match="No reliable"):
        analyse_trace(samples([None, None]), Plan())


def test_degenerate_geometry_and_plan_bounds():
    assert interior_angle((0, 0), (0, 0), (1, 0)) is None
    with pytest.raises(ValueError):
        Plan(upper_angle=80)
