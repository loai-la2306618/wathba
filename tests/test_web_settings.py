from fastapi.testclient import TestClient
from wathba import storage, webapp
from wathba.motion import Plan


def test_older_report_gets_a_matched_count_without_rewriting_history(tmp_path, monkeypatch):
    plan = Plan(reference_id="b" * 32).dict()
    samples = [{"time": i * .5, "angle": angle, "confidence": .95} for i, angle in enumerate([90, 120, 90])]
    cycle = {"rep": 1, "start": 0, "end": 1, "duration": 1, "sample_start": 0, "sample_end": 2, "findings": []}
    cycles = [cycle, {**cycle, "rep": 2, "findings": [{"kind": "range"}]}]
    session = {"id": "a" * 32, "plan": plan, "samples": samples, "cycles": cycles,
               "reference_model": {"reference_session_id": "b" * 32}, "coverage": 100,
               "exercise": "Squat", "repetitions": 2, "duration": 2, "created_at": "2026-11-06T10:00:00Z",
               "source_video": str(tmp_path / "source.mp4"), "annotated_video": str(tmp_path / "annotated.mp4"),
               "model": "test", "feedback": "", "flags": []}
    monkeypatch.setattr(storage, "load_reference", lambda _: {"templates": {"knee_angle": {}}})
    monkeypatch.setattr(storage, "load", lambda _: {"source_video": str(tmp_path / "reference.mp4")})
    monkeypatch.setattr(storage, "folder", lambda _: tmp_path)
    monkeypatch.setattr(webapp, "media_url", str)
    monkeypatch.setattr(webapp, "session_analysis", lambda _: {})
    monkeypatch.setattr(webapp, "replay_rows", lambda _: [])
    result = webapp.public_session(session)
    assert result["accepted_repetitions"] == 1
    assert result["cycles"][0]["accepted"] is True
    assert result["cycles"][1]["accepted"] is False
    assert "accepted" not in cycles[0]


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
