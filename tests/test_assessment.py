import math

import numpy as np
import pytest

from wathba.assessment import assess, fit_reference, pose_features, segment_cycles
from wathba.motion import Plan


def recording(durations=(3, 3, 3, 3), amplitudes=None, offset=85, polarity=1, torso_offset=0):
    amplitudes = amplitudes or [65] * len(durations)
    samples, total = [], sum(durations)
    for t in np.arange(0, total + .16, 1 / 8):
        start = 0
        angle = offset
        for duration, amplitude in zip(durations, amplitudes):
            if t <= start + duration:
                phase = (t - start) / duration
                angle = offset + polarity * amplitude * (1 - math.cos(2 * math.pi * phase)) / 2
                break
            start += duration
        features = {"knee_angle": angle, "torso_lean": 8 + torso_offset, "hip_angle": 100 + .2 * (angle - offset)}
        samples.append({"time": float(t), "angle": angle, "confidence": .95, "features": features,
                        "feature_confidence": {k: .95 for k in features}})
    return samples


def reference(samples=None):
    session = {"id": "a" * 32, "plan": Plan().dict(), "exercise": Plan().exercise, "samples": samples or recording(),
               "duration": 12, "synthetic": False}
    return fit_reference(session, approved=True, cues={"pace": "Match the pace assigned by your physiotherapist."})


def test_adaptive_count_does_not_require_original_demo_angles():
    samples = recording(offset=120, amplitudes=[25] * 4)
    assert len(segment_cycles(samples)) == 4


def test_can_start_at_either_end_of_movement():
    assert len(segment_cycles(recording(offset=170, polarity=-1))) == 4


def test_observed_final_return_is_not_erased_by_smoothing():
    angles = [85, 85, 100, 145, 155, 140, 135, 92]
    samples = [{"time": i * .25, "angle": angle, "confidence": .95} for i, angle in enumerate(angles)]
    assert len(segment_cycles(samples, polarity=1)) == 1


def test_partial_repetitions_are_not_completed_at_reference_phase_edges():
    samples = recording()
    trimmed = samples[7:-7]
    assert len(segment_cycles(trimmed, polarity=1)) == 2


def test_reference_comparison_identifies_fast_and_short_cycles():
    model = reference()
    samples = recording(durations=(3, 1.3, 3, 3), amplitudes=[65, 65, 32, 65])
    result = assess(samples, Plan(), model)
    assert result["repetitions"] == 4
    assert any(f["kind"] == "pace" for flag in result["flags"] for f in flag["evidence"])
    assert any(f["kind"] == "range" for flag in result["flags"] for f in flag["evidence"])
    assert any("Match the pace" in flag["cue"] for flag in result["flags"])


def test_normal_reference_like_motion_is_not_flagged_as_wrong():
    result = assess(recording(durations=(3.1, 2.9, 3.05, 3)), Plan(), reference())
    assert result["repetitions"] == 4
    assert not result["flags"]


def test_trunk_difference_is_separate_from_knee_range():
    result = assess(recording(torso_offset=24), Plan(), reference())
    assert any(f["feature"] == "torso_lean" for flag in result["flags"] for f in flag["evidence"])


def test_no_reference_produces_measurements_without_fabricated_corrections():
    result = assess(recording(durations=(3, 1, 3, 3)), Plan())
    assert result["repetitions"] == 4
    assert result["flags"] == []
    assert result["reference_model"] is None
    assert "Measurements only" in result["assessment_status"]


def test_tracking_gap_does_not_complete_a_repetition():
    samples = recording()
    for s in samples:
        if 1 < s["time"] < 2:
            s["feature_confidence"]["knee_angle"] = .1
    result = assess(samples, Plan(), reference())
    assert result["repetitions"] == 3
    assert any(f["kind"] == "tracking" for f in result["flags"])


def test_incompatible_reference_and_synthetic_reference_are_rejected():
    model = reference()
    model["view"] = "Front"
    with pytest.raises(ValueError, match="match"):
        assess(recording(), Plan(), model)
    model = reference()
    model["synthetic"] = True
    with pytest.raises(ValueError, match="synthetic"):
        assess(recording(), Plan(), model)
    model = reference()
    with pytest.raises(ValueError, match="tracked leg"):
        assess(recording(), Plan(side="Right"), model)


def test_joint_confidence_does_not_spread_to_other_features():
    points = np.zeros((17, 2))
    points[6], points[12], points[14], points[16] = [100, 100], [100, 200], [150, 200], [150, 300]
    scores = np.ones(17) * .95
    scores[16] = .1
    features, _ = pose_features(points, scores, "Right")
    assert features["knee_angle"] is None
    assert features["torso_lean"] == 0


def test_explicit_illustrative_comparison_retains_provenance():
    model = reference()
    model["synthetic"] = True
    model["approved_by_user"] = False
    result = assess(recording(), Plan(allow_illustrative_reference=True), model)
    assert result["assessment_status"] == "Illustrative reference comparison"
    assert result["reference_model"]["synthetic"] is True
    assert any("illustrated research" in note for note in result["limitations"])


def test_one_repetition_is_not_enough_for_reference_variation():
    with pytest.raises(ValueError, match="at least two"):
        reference(recording(durations=(3,)))
