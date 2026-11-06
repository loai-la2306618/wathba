import json
import zipfile

import cv2

from wathba import storage
from wathba.motion import Plan
from wathba.pipeline import example_session
from wathba.presentation import summary_html
from wathba.reporting import bundle
from wathba.assessment import fit_reference


def test_video_to_clip_to_clinician_review(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    session = example_session(Plan())
    assert session["synthetic"] is True
    assert "no AI inference" in session["model"]
    assert session["repetitions"] == 5
    assert {f["kind"] for f in session["flags"]} == {"pace", "range", "tracking"}
    for flag in session["flags"]:
        cap = cv2.VideoCapture(flag["clip"])
        assert cap.isOpened()
        assert cap.get(cv2.CAP_PROP_FRAME_COUNT) > 0
        clip_duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        assert abs(clip_duration - (flag["clip_end"] - flag["clip_start"])) < .25
    flag = session["flags"][0]
    storage.review(session["id"], flag["id"], "Dismissed", "Camera perspective; review again.")
    storage.feedback(session["id"], "Please follow the plan assigned at your appointment.")
    reloaded = storage.load(session["id"])
    assert reloaded["flags"][0]["status"] == "Dismissed"
    assert reloaded["feedback"].startswith("Please follow")
    assert reloaded["plan"] == Plan().dict()
    storage.save_plan(Plan(target_repetitions=8))
    assert storage.load_plan().target_repetitions == 8
    assert storage.load(session["id"])["plan"]["target_repetitions"] == 5
    assert json.loads((storage.folder(session["id"]) / "report.json").read_text())["synthetic"]
    model = fit_reference(session)
    model_path = storage.save_reference(model)
    assert storage.load_reference(session["id"]) == json.loads(open(model_path).read())
    archive_path = bundle(reloaded, storage.folder(session["id"]))
    with zipfile.ZipFile(archive_path) as archive:
        exported = json.loads(archive.read("report.json"))
        readable = archive.read("physio-report.html").decode()
        assert "Camera perspective; review again." in readable
        assert reloaded["feedback"] in readable
        assert "synthetic illustrated research guide" in readable
        assert "Awaiting review." not in readable
        for flag in exported["flags"]:
            assert "/" not in flag["clip"]
            assert archive.read(flag["clip"])


def test_report_escapes_user_content(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    session = example_session(Plan())
    session["symptoms"] = '<img src=x onerror="alert(1)">'
    assert "<img" not in summary_html(session)
    assert "&lt;img" in summary_html(session)
