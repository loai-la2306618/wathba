from fastapi.testclient import TestClient

from wathba import storage, webapp


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(webapp, 'prepare_library', lambda: tmp_path)
    return TestClient(webapp.create_app())


def test_reference_from_before_a_restart_is_not_treated_as_known(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    assert not webapp.known_reference('a' * 32)
    assert not webapp.known_reference(None)


def test_locked_demo_rejects_a_new_reference(tmp_path, monkeypatch):
    monkeypatch.setenv('WATHBA_LOCK_REFERENCE', '1')
    rows = [{'time': i / 6, 'keypoints': None} for i in range(6)]
    r = client(tmp_path, monkeypatch).post('/api/process', json={'asset': 'therapist', 'rows': rows, 'reference': True, 'consent': True})
    assert r.status_code == 403
    assert client(tmp_path, monkeypatch).get('/api/config').json()['referenceLocked'] is True


def test_reference_is_open_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv('WATHBA_LOCK_REFERENCE', raising=False)
    assert client(tmp_path, monkeypatch).get('/api/config').json()['referenceLocked'] is False


def test_failed_reference_rebuild_does_not_stop_the_app(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(webapp, 'reference_id', lambda *_: None)
    (tmp_path / 'therapist-squat.mp4').write_bytes(b'x')
    monkeypatch.setattr(webapp, 'process_browser_video', lambda *a, **k: (_ for _ in ()).throw(ValueError('bad rows')))
    webapp.seed_reference(tmp_path)
