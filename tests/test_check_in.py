from fastapi.testclient import TestClient

from wathba import storage, webapp
from wathba.reporting import render_report


def make_session(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(webapp, 'prepare_library', lambda: tmp_path)
    session = {'schema_version': 2, 'id': 'e'*32, 'created_at': '2026-11-06T16:00:00+00:00', 'label': 'Patient squat session',
               'exercise': 'Squat', 'plan': {'side': 'Left', 'view': 'Front', 'target_repetitions': 5, 'reference_id': None},
               'samples': [], 'source_video': str(tmp_path/'s.mp4'), 'annotated_video': str(tmp_path/'s.mp4'), 'duration': 10,
               'feedback': '', 'model': 'test', 'pose_engine': 'wathba-pose-coco17-v1', 'height_normalisation': 'static_torso_v1',
               'synthetic': False, 'symptoms': '', 'reported_pain': None, 'repetitions': 3, 'cycles': [], 'flags': [], 'coverage': 100,
               'match_score': {'value': None, 'reason': 'n/a'}, 'limitations': []}
    (tmp_path/session['id']).mkdir()
    storage.save(session)
    return TestClient(webapp.create_app()), session['id']


def test_check_in_is_saved_flagged_and_shown_in_report_and_history(tmp_path, monkeypatch):
    client, sid = make_session(tmp_path, monkeypatch)
    r = client.post(f'/api/session/{sid}/check-in', json={'pain_during': True, 'pain_after': 6, 'pain_locations': ['knee', 'knee'],
                                                         'difficulty': 'hard', 'knee_unstable': True, 'swelling': False, 'notes': ' tight '})
    assert r.status_code == 200
    ci = r.json()['check_in']
    assert ci['pain_locations'] == ['knee'] and ci['notes'] == 'tight'
    assert ci['attention'] == ['pain_after', 'knee_unstable']
    saved = storage.load(sid)
    assert saved['reported_pain'] == 6 and saved['symptoms'] == 'tight'
    html = render_report(saved)
    assert 'How the patient felt' in html and '6/10' in html and 'Needs attention' in html and 'يحتاج إلى متابعة' in html
    assert html.index('How the patient felt') < html.index('Technical details')
    history = client.get('/api/history').json()
    assert history[0]['pain'] == 6 and history[0]['attention'] == ['pain_after', 'knee_unstable']


def test_skipped_questions_stay_unanswered(tmp_path, monkeypatch):
    client, sid = make_session(tmp_path, monkeypatch)
    ci = client.post(f'/api/session/{sid}/check-in', json={}).json()['check_in']
    assert ci['pain_after'] is None and ci['pain_during'] is None and ci['attention'] == []
    assert 'Not answered' in render_report(storage.load(sid))


def test_invalid_answers_are_rejected(tmp_path, monkeypatch):
    client, sid = make_session(tmp_path, monkeypatch)
    for bad in ({'pain_after': 11}, {'pain_after': -1}, {'pain_locations': ['shoulder']}, {'difficulty': 'extreme'}, {'notes': 'x'*1001}):
        assert client.post(f'/api/session/{sid}/check-in', json=bad).status_code == 422
    assert client.post('/api/session/' + 'f'*32 + '/check-in', json={}).status_code == 404
