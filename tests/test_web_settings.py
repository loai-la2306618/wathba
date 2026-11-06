from fastapi.testclient import TestClient
from wathba import storage, webapp
from wathba.motion import Plan


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(webapp, 'prepare_library', lambda: tmp_path)
    return TestClient(webapp.create_app())


def test_program_change_persists_and_bounds_are_enforced(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.post('/api/program', json={'target_repetitions': 8}).status_code == 200
    assert storage.load_plan().target_repetitions == 8
    assert c.get('/api/config').json()['target'] == 8
    assert c.post('/api/program', json={'target_repetitions': 0}).status_code == 422
    assert c.post('/api/program', json={'target_repetitions': 51}).status_code == 422
    assert storage.load_plan().target_repetitions == 8


def test_feedback_for_missing_session_is_not_written(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.post('/api/session/'+'a'*32+'/feedback', json={'text':'Review note'}).status_code == 404
    assert not (tmp_path/('a'*32)).exists()


def test_exercises_have_separate_sources_and_reference_slots(tmp_path, monkeypatch):
    c=client(tmp_path,monkeypatch)
    squat=c.get('/api/config?exercise=squat').json()
    jump=c.get('/api/config?exercise=jump').json()
    assert squat['exercise']=='Squat' and jump['exercise']=='Jump'
    assert jump['referenceId'] is None and jump['comparisonAvailable'] is False
    assert c.get('/api/config?exercise=other').status_code==400
    assert c.get('/api/demo-program').json()['total']==2
    response=c.post('/api/process',json={'exercise':'jump','asset':'patient','rows':[{}]*5,'consent':True})
    assert response.status_code==404
