import json

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


def test_saved_sessions_are_reread_only_when_they_change(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path, raising=False)
    folder = tmp_path / 'a'
    folder.mkdir()
    report = folder / 'report.json'
    report.write_text(json.dumps({'id': 'a', 'created_at': '1', 'label': 'first'}), encoding='utf-8')
    assert storage.sessions()[0]['label'] == 'first'
    storage.sessions()[0]['label'] = 'changed by a caller'
    assert storage.sessions()[0]['label'] == 'first'
    report.write_text(json.dumps({'id': 'a', 'created_at': '1', 'label': 'second one'}), encoding='utf-8')
    assert storage.sessions()[0]['label'] == 'second one'
    report.unlink()
    assert storage.sessions() == []


def test_mp4_writer_makes_a_playable_video_from_odd_sized_frames(tmp_path):
    import cv2
    import numpy as np
    from wathba.media import Mp4Writer
    output = tmp_path / 'out.mp4'
    writer = Mp4Writer(output, (101, 75), 15)
    for _ in range(10):
        writer.write(np.zeros((75, 101, 3), np.uint8))
    writer.close()
    cap = cv2.VideoCapture(str(output))
    assert cap.read()[0] and int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) == 100
    cap.release()
