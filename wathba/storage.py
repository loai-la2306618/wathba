"""A shared demo workspace. IDs are server generated, and writes are atomic."""

import json
import os
import re
import threading
import uuid
from pathlib import Path

ROOT = Path(os.getenv("WATHBA_DATA_DIR", ".wathba")).resolve()
LOCK = threading.RLock()


def root():
    ROOT.mkdir(parents=True, exist_ok=True)
    return ROOT


def folder(session_id):
    if not re.fullmatch(r"[0-9a-f]{32}", session_id):
        raise ValueError("Invalid session identifier.")
    return root() / session_id


def new_folder():
    session_id = uuid.uuid4().hex
    path = folder(session_id)
    path.mkdir()
    return session_id, path


def save(session):
    with LOCK:
        path = folder(session["id"]) / "report.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(session, ensure_ascii=False, indent=2, allow_nan=False))
        tmp.replace(path)
        from .reporting import write_report
        write_report(session, path.parent)
    return str(path)


def load(session_id):
    with LOCK:
        from . import remote
        if remote.enabled():remote.ensure(f"{session_id}/report.json",check=True)
        data=json.loads((folder(session_id) / "report.json").read_text())
        return remote.rebase(data) if remote.enabled() else data


def sessions():
    from . import remote
    remote.refresh_reports()
    result = []
    for path in root().glob("*/report.json"):
        try:
            session = json.loads(path.read_text())
            result.append(remote.rebase(session) if remote.enabled() else session)
        except (ValueError, OSError):
            continue
    return sorted(result, key=lambda s: s["created_at"], reverse=True)


def review(session_id, flag_id, status, comment):
    if status not in ("Pending", "Confirmed", "Dismissed"):
        raise ValueError("Unknown review status.")
    with LOCK:
        session = load(session_id)
        flag = next((f for f in session["flags"] if f["id"] == flag_id), None)
        if flag is None:
            raise ValueError("Choose a flagged moment first.")
        flag.update(status=status, comment=comment[:2000])
        save(session)
    return session


def feedback(session_id, text):
    with LOCK:
        session = load(session_id)
        session["feedback"] = text[:5000]
        save(session)
    return session


def load_plan():
    from .motion import Plan
    path = root() / "plan.json"
    from . import remote
    if remote.enabled():remote.ensure("plan.json",refresh=True)
    return Plan(**json.loads(path.read_text())) if path.exists() else Plan()


def save_plan(plan):
    with LOCK:
        path = root() / "plan.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(plan.dict()))
        tmp.replace(path)
        from . import remote
        remote.persist_file(path)


def references():
    items = []
    for path in root().glob("*/motion-model.json"):
        try:
            model = json.loads(path.read_text())
            items.append(model)
        except (ValueError, OSError):
            continue
    return items


def save_reference(model):
    path = folder(model["reference_session_id"]) / "motion-model.json"
    with LOCK:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False))
        tmp.replace(path)
    return str(path)


def load_reference(session_id):
    folder(session_id)
    from . import remote
    if remote.enabled():remote.ensure(f"{session_id}/motion-model.json")
    return json.loads((folder(session_id) / "motion-model.json").read_text())
