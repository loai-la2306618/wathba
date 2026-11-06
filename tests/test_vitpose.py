import importlib.util
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from wathba import storage, vitpose_service, webapp
from wathba.pose_schema import JOINTS, PIPELINE

BODY = {'left_shoulder': (.55, .2), 'right_shoulder': (.45, .2), 'left_hip': (.53, .5), 'right_hip': (.47, .5),
        'left_knee': (.56, .7), 'right_knee': (.44, .7), 'left_ankle': (.55, .9), 'right_ankle': (.45, .9)}


def named(offset=0.0, confidence=.9):
    kp = {n: {'x': .5, 'y': .1, 'z': None, 'confidence': confidence} for n in JOINTS}
    for n, (x, y) in BODY.items():
        kp[n].update(x=x + offset, y=y)
    return kp


def test_box_is_converted_to_clipped_coco_pixels():
    assert vitpose_service.box_to_coco([-.1, .1, .5, 1.2], 200, 400) == [0.0, 40.0, 100.0, 360.0]
    with pytest.raises(ValueError):
        vitpose_service.box_to_coco([.5, .5, .51, .51], 200, 400)
    with pytest.raises(ValueError):
        vitpose_service.box_to_coco(None, 200, 400)


def test_vitpose_pixels_map_to_named_schema_without_depth():
    points = np.array([[100, 200]] * 17, float); points[0] = [-5, 10]
    kp = vitpose_service.to_schema(points, np.full(17, .8), 200, 400)
    assert kp['nose'] is None, 'outside the frame is missing, not clamped'
    assert kp['left_hip'] == {'x': .5, 'y': .5, 'z': None, 'confidence': pytest.approx(.8)}


def make_session(tmp_path, with_boxes=True):
    import cv2
    from wathba.browser_pose import browser_samples
    from wathba.motion import Plan
    video = tmp_path/'source.mp4'
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 6, (200, 400))
    for _ in range(12):
        writer.write(np.full((400, 200, 3), 90, np.uint8))
    writer.release()
    rows = [{'time': i/6, 'model': 'movenet-singlepose-lightning', 'trackId': 'person-1', 'detector': 'yolov8n-pose',
             'keypoints': named(), 'box': [.3, .1, .7, .95] if with_boxes else None} for i in range(12)]
    samples = browser_samples(rows, 200, 400, 2, Plan(view='Front', primary_feature='hip_height'))
    return {'id': 'a'*32, 'plan': {'side': 'Left'}, 'samples': samples, 'source_video': str(video), 'pose_engine': PIPELINE,
            'keypoint_model': 'movenet-singlepose-lightning',
            'cycles': [{'rep': 1, 'start': 0.0, 'peak_time': 1.0, 'end': 1.8}]}


def test_check_uses_tracker_boxes_and_keeps_model_outputs_separate(tmp_path):
    session = make_session(tmp_path)
    seen = []

    def fake(frame, box):
        seen.append((frame.shape, box))
        return named(offset=.02, confidence=.7)  # ViTPose places joints 4 px to the right
    result = vitpose_service.check_session(session, estimator=fake)
    assert [c['phase'] for c in result['checkpoints']] == ['start', 'peak']
    assert all(box == [.3, .1, .7, .95] and shape == (400, 200, 3) for shape, box in seen)
    c = result['checkpoints'][0]
    assert c['browser']['model'] == 'movenet-singlepose-lightning'
    assert c['browser']['features']['torso_lean'] != c['vitpose']['features']['torso_lean'] or c['difference']['torso_lean'] == 0
    assert c['difference']['knee_angle'] == pytest.approx(c['vitpose']['features']['knee_angle'] - c['browser']['features']['knee_angle'], abs=1e-3)
    assert result['summary']['knee_offset']['compared'] == 2
    assert 'does not establish accuracy' in result['note']


def test_check_without_person_boxes_is_refused(tmp_path):
    with pytest.raises(ValueError, match='person boxes'):
        vitpose_service.check_session(make_session(tmp_path, with_boxes=False), estimator=lambda *_: named())


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(webapp, 'prepare_library', lambda: tmp_path)
    return TestClient(webapp.create_app())


def test_endpoint_requires_consent_and_reports_unavailable_backend(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    url = '/api/session/' + 'b'*32 + '/vitpose-check'
    assert c.post(url, json={}).status_code == 400
    monkeypatch.setattr(vitpose_service, 'available', lambda: (False, 'ViTPose needs optional backend packages'))
    r = c.post(url, json={'consent': True})
    assert r.status_code == 503 and 'optional backend' in r.json()['detail']
    assert c.get('/api/config').json()['pose']['vitpose'] == {'available': False, 'reason': 'ViTPose needs optional backend packages'}


def test_endpoint_saves_separate_model_check(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    session = make_session(tmp_path)
    session.update(id='c'*32, created_at='2026-11-06T00:00:00+00:00', label='t', exercise='Squat', flags=[], feedback='')
    (tmp_path/session['id']).mkdir()
    monkeypatch.setattr('wathba.reporting.write_report', lambda *_: None)
    storage.save(session)
    monkeypatch.setattr(vitpose_service, 'available', lambda: (True, ''))
    monkeypatch.setattr(vitpose_service, 'check_session', lambda s: {'model': 'vitpose-base-simple', 'checkpoints': [], 'summary': {}})
    r = c.post(f"/api/session/{session['id']}/vitpose-check", json={'consent': True})
    assert r.status_code == 200
    saved = storage.load(session['id'])
    assert saved['model_checks']['vitpose']['model'] == 'vitpose-base-simple'
    legacy = {**session, 'id': 'd'*32, 'pose_engine': 'mediapipe-pose-landmarker-full'}
    (tmp_path/legacy['id']).mkdir()
    storage.save(legacy)
    assert c.post(f"/api/session/{legacy['id']}/vitpose-check", json={'consent': True}).status_code == 400


def test_failed_model_load_is_reported_not_simulated(monkeypatch):
    monkeypatch.setitem(vitpose_service._state, 'error', None)
    monkeypatch.setitem(vitpose_service._state, 'model', None)
    monkeypatch.setattr(vitpose_service, 'available', lambda: (True, ''))
    import builtins
    real_import = builtins.__import__

    def broken(name, *args, **kwargs):
        if name == 'transformers':
            raise ImportError('simulated broken install')
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', broken)
    with pytest.raises(vitpose_service.Unavailable, match='could not be loaded'):
        vitpose_service.load()
    monkeypatch.setitem(vitpose_service._state, 'error', None)


REAL = importlib.util.find_spec('torch') and importlib.util.find_spec('transformers') and os.getenv('WATHBA_TEST_VIDEO')


@pytest.mark.skipif(not REAL, reason='Set WATHBA_TEST_VIDEO and install requirements-vitpose.txt to run the real ViTPose check.')
def test_real_vitpose_on_a_frontal_frame():
    import cv2
    cap = cv2.VideoCapture(os.environ['WATHBA_TEST_VIDEO'])
    ok, frame = cap.read(); cap.release()
    assert ok
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    box = [float(v) for v in os.getenv('WATHBA_TEST_BOX', '0.2,0.15,0.75,0.65').split(',')]
    kp = vitpose_service.estimate(rgb, box)
    assert set(kp) == set(JOINTS)
    hips = kp['left_hip'], kp['right_hip']
    assert all(h and h['confidence'] >= .3 for h in hips)
    # Facing the camera, the subject's anatomical left appears on the image right.
    assert kp['left_hip']['x'] > kp['right_hip']['x']
    assert all(k is None or k['z'] is None for k in kp.values())
