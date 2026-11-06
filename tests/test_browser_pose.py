import copy
import math

import pytest

from wathba.browser_pose import browser_samples, compatible_reference
from wathba.motion import Plan
from wathba.pose_schema import JOINTS, PIPELINE, legacy_mediapipe_row, replay_rows, threshold, unavailable_measurements

MOVENET = 'movenet-singlepose-lightning'
YOLO = 'yolov8n-pose'


def test_missing_joints_can_be_saved_as_json():
    from wathba.storage import json_safe
    safe = json_safe({'samples': [{'points': [[1.0, math.nan], [math.inf, 2.0]], 'scores': (0.5, 0.0)}]})
    assert safe == {'samples': [{'points': [[1.0, None], [None, 2.0]], 'scores': [0.5, 0.0]}]}

BODY = {'left_shoulder': (.4, .2), 'right_shoulder': (.6, .2), 'left_hip': (.45, .5), 'right_hip': (.55, .5),
        'left_knee': (.4, .7), 'right_knee': (.6, .7), 'left_ankle': (.4, .9), 'right_ankle': (.6, .9)}


def keypoints(confidence=.95):
    kp = {name: {'x': .5, 'y': .5, 'z': None, 'confidence': confidence} for name in JOINTS}
    for name, (x, y) in BODY.items():
        kp[name].update(x=x, y=y)
    return kp


def rows(model=MOVENET, n=6, step=.2, confidence=.95):
    return [{'schema': 'wathba.pose/1', 'time': i*step, 'frameId': i+1, 'trackId': 'person-1', 'model': model,
             'detector': YOLO, 'keypoints': keypoints(confidence), 'box': [.3, .1, .7, .95]} for i in range(n)]


def test_named_joints_preserve_left_leg_and_pixel_aspect():
    result = browser_samples(rows(), 400, 800, 1, Plan(view='Front', primary_feature='hip_height'))
    left_hip, left_knee = JOINTS.index('left_hip'), JOINTS.index('left_knee')
    assert result[0]['points'][left_hip] == [180, 400]
    assert result[0]['points'][left_knee] == [160, 560]
    assert result[0]['features']['hip_height'] == pytest.approx(1.3333)
    assert result[0]['pose_model'] == MOVENET and result[0]['box'] == [.3, .1, .7, .95]


def test_missing_person_is_uncertain_not_substituted():
    data = rows(); data[2]['keypoints'] = None
    result = browser_samples(data, 400, 800, 1, Plan())
    assert result[2]['points'] is None
    assert result[2]['confidence'] == 0


def test_missing_joint_is_never_filled():
    data = rows()
    for r in data:
        r['keypoints']['left_knee'] = None
    result = browser_samples(data, 400, 800, 1, Plan(view='Front', primary_feature='hip_height'))
    assert all(math.isnan(v) for v in result[0]['points'][JOINTS.index('left_knee')])
    assert result[0]['reliable'][JOINTS.index('left_knee')] is False
    assert result[0]['features']['knee_offset'] is None and result[0]['features']['knee_angle'] is None
    assert result[0]['features']['hip_height'] is not None  # does not need the knee


def test_confidence_thresholds_are_per_model_not_shared():
    assert threshold(MOVENET) == .3 and threshold(YOLO) == .5
    movenet = browser_samples(rows(MOVENET, confidence=.4), 400, 800, 1, Plan(view='Front', primary_feature='hip_height'))
    yolo = browser_samples(rows(YOLO, confidence=.4), 400, 800, 1, Plan(view='Front', primary_feature='hip_height'))
    assert movenet[0]['features']['hip_height'] is not None
    assert yolo[0]['features']['hip_height'] is None


def test_mixed_keypoint_models_in_one_recording_are_rejected():
    data = rows(); data[3]['model'] = YOLO
    with pytest.raises(ValueError, match='one keypoint model'):
        browser_samples(data, 400, 800, 1, Plan())


def test_other_tracked_person_is_not_stitched_into_the_series():
    data = rows(n=8, step=1/7); data[6]['trackId'] = data[7]['trackId'] = 'person-2'
    result = browser_samples(data, 400, 800, 1, Plan(view='Front', primary_feature='hip_height'))
    assert result[6]['points'] is None and result[6]['tracking_reason'] == 'Different tracked person'
    assert result[0]['features']['hip_height'] is not None


@pytest.mark.parametrize('failure', ['unknown_joint', 'nan', 'depth', 'time_reversal', 'partial_video', 'schema', 'model'])
def test_invalid_or_partial_browser_tracking_is_rejected(failure):
    data = rows(); duration = 1
    if failure == 'unknown_joint': data[0]['keypoints']['left_heel'] = {'x': .4, 'y': .95, 'confidence': .9}
    if failure == 'nan': data[0]['keypoints']['left_hip']['x'] = float('nan')
    if failure == 'depth': data[0]['keypoints']['left_hip']['z'] = .1
    if failure == 'time_reversal': data[3]['time'] = .1
    if failure == 'partial_video': duration = 10
    if failure == 'schema': data[0]['schema'] = 'mediapipe'
    if failure == 'model':
        for r in data: r['model'] = 'mediapipe-pose-landmarker-full'
    with pytest.raises(ValueError):
        browser_samples(data, 400, 800, duration, Plan())


def test_torso_foreshortening_does_not_create_squat_cycles():
    from wathba.assessment import segment_cycles
    data = []
    for i in range(73):
        kp = keypoints()
        y = .2 + .12*(1 - math.cos(2*math.pi*i/18))/2
        kp['left_shoulder']['y'] = kp['right_shoulder']['y'] = y
        data.append({'time': i/6, 'model': MOVENET, 'trackId': 'person-1', 'keypoints': kp})
    samples = browser_samples(data, 400, 800, 12, Plan(view='Front', primary_feature='hip_height'))
    assert max(s['features']['hip_height'] for s in samples) - min(s['features']['hip_height'] for s in samples) < .001
    assert not segment_cycles(samples, 'hip_height')


def test_squat_does_not_count_as_jump_when_feet_stay_on_floor():
    from wathba.assessment import segment_cycles
    data = []
    for i in range(145):
        kp = keypoints()
        offset = .12*(1 - math.cos(2*math.pi*i/36))/2
        for j in ('left_shoulder', 'right_shoulder', 'left_hip', 'right_hip'):
            kp[j]['y'] += offset
        data.append({'time': i/12, 'model': MOVENET, 'keypoints': kp})
    samples = browser_samples(data, 400, 800, 12, Plan(exercise='Jump', view='Front', primary_feature='foot_lift', sample_fps=12))
    assert max(abs(s['features']['foot_lift']) for s in samples) < .001
    assert not segment_cycles(samples, 'foot_lift')


def test_jump_lift_is_distinct_from_squat_and_detects_complete_jumps():
    from wathba.assessment import segment_cycles
    data = []
    for i in range(145):
        kp = keypoints()
        phase = (i % 48)/48
        lift = .12*max(0, math.sin(2*math.pi*(phase - .2)))
        for v in kp.values():
            v['y'] -= lift
        data.append({'time': i/12, 'model': MOVENET, 'keypoints': kp})
    samples = browser_samples(data, 400, 800, 12, Plan(exercise='Jump', view='Front', primary_feature='foot_lift', sample_fps=12))
    assert len(segment_cycles(samples, 'foot_lift')) == 3


def test_low_confidence_occlusion_pauses_measurement_instead_of_guessing():
    from wathba.assessment import assess
    data = []
    for i in range(60):
        kp = keypoints()
        kp['left_hip']['y'] = kp['right_hip']['y'] = .5 + .1*(1 - math.cos(2*math.pi*i/20))/2
        if 25 <= i < 40:  # legs occluded: ankles drop below MoveNet's threshold
            kp['left_ankle']['confidence'] = kp['right_ankle']['confidence'] = .1
        data.append({'time': i/6, 'model': MOVENET, 'trackId': 'person-1', 'keypoints': kp})
    plan = Plan(view='Front', primary_feature='hip_height')
    samples = browser_samples(data, 400, 800, 10, plan)
    assert all(s['features']['hip_height'] is None for s in samples[25:40])
    result = assess(samples, plan)
    assert any(f['kind'] == 'tracking' and 4 <= f['start'] <= 4.3 for f in result['flags'])
    assert result['coverage'] == pytest.approx(75.0)


def test_reference_from_another_model_or_engine_is_not_compared():
    current = {'pose_engine': PIPELINE, 'height_normalisation': 'static_torso_v1', 'keypoint_model': MOVENET}
    assert compatible_reference(current, MOVENET) == (current, None)
    ref, reason = compatible_reference(current, YOLO)
    assert ref is None and 'not compared' in reason
    ref, reason = compatible_reference({**current, 'pose_engine': 'mediapipe-pose-landmarker-full'}, MOVENET)
    assert ref is None and 'earlier pose engine' in reason


def test_legacy_mediapipe_record_remains_replayable_as_named_joints():
    landmarks = [{'x': i/40, 'y': .5, 'z': -.2, 'visibility': .9} for i in range(33)]
    row = legacy_mediapipe_row({'time': 1.0, 'landmarks': landmarks})
    assert row['keypoints']['left_hip']['x'] == 23/40 and row['keypoints']['left_hip']['z'] is None
    assert set(row['keypoints']) == set(JOINTS)
    assert legacy_mediapipe_row({'time': 2.0, 'landmarks': []})['keypoints'] is None
    session = {'pose_engine': 'mediapipe-pose-landmarker-full', 'browser_landmarks': [{'time': 1.0, 'landmarks': landmarks}]}
    assert replay_rows(session)[0]['model'] == 'mediapipe-legacy-record'


def test_depth_and_foot_measurements_are_reported_unavailable():
    ids = {m['id'] for m in unavailable_measurements()}
    assert {'depth', 'world_coordinates', 'knee_flexion_3d', 'heel_toe_contact'} <= ids


def test_untrackable_patient_attempt_is_still_saved_for_review(tmp_path, monkeypatch):
    import cv2, numpy as np
    from wathba import storage
    from wathba.browser_pose import process_browser_video
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    source = tmp_path/'attempt.mp4'
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 6, (160, 160))
    for _ in range(12):
        writer.write(np.zeros((160, 160, 3), np.uint8))
    writer.release()
    data = [{'time': i/6, 'keypoints': None, 'model': None} for i in range(12)]
    session = process_browser_video(source, data, exercise='jump')
    saved = storage.load(session['id'])
    assert saved['repetitions'] == 0 and saved['match_score']['value'] is None
    assert saved['flags'][0]['kind'] == 'assessment'
    assert saved['source_video'] and saved['flags'][0]['picture']
    assert saved['pose_engine'] == PIPELINE and saved['keypoint_model'] is None
