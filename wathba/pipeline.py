"""Video-to-review workflow and an explicitly synthetic example."""

import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from . import storage
from .assessment import assess, fit_reference
from .media import clip_video
from .scoring import reference_match, counted_repetitions


def evidence_picture(source, destination, timestamp):
    import cv2
    cap = cv2.VideoCapture(str(source))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0, timestamp)*1000)
    ok, frame = cap.read()
    cap.release()
    if ok and cv2.imwrite(str(destination), frame):
        return str(destination)
    return None


def finish(session_id, directory, samples, plan, source, annotated, duration, label, symptoms, pain, synthetic, elapsed, reference=None):
    metrics = assess(samples, plan, reference, illustrative=synthetic)
    metrics["match_score"] = reference_match(samples, metrics["cycles"], reference, metrics["coverage"])
    metrics["counted_repetitions"] = counted_repetitions(metrics["cycles"], metrics["match_score"])
    ref_session = None
    if reference and not reference.get('synthetic'):
        try:
            ref_session = storage.load(reference['reference_session_id'])
            from . import remote
            if remote.enabled():remote.ensure(ref_session['annotated_video'])
        except (OSError, ValueError):
            pass
    for flag in metrics["flags"]:
        clip, start, end = clip_video(annotated, directory / f"{flag['id']}.mp4", flag["start"], flag["end"], duration)
        flag.update(clip=clip, clip_start=start, clip_end=end)
        worst = max(flag.get('evidence', []), key=lambda e: (e.get('severity')=='red', e.get('peak_difference',0)), default={})
        timestamp = worst.get('time', (flag['start']+flag['end'])/2)
        flag['picture_time'] = timestamp
        picture = evidence_picture(annotated, directory/f"{flag['id']}.jpg", timestamp)
        if picture:flag['picture'] = picture
        if ref_session:
            ref_cycle = (ref_session.get('cycles') or [{}])[0]
            ref_time = ref_cycle.get('start',0)+worst.get('reference_phase',.5)*ref_cycle.get('duration',0)
            picture = evidence_picture(ref_session['annotated_video'], directory/f"{flag['id']}-reference.jpg", ref_time)
            if picture:flag['reference_picture'] = picture
    session = {"schema_version": 2, "id": session_id, "created_at": datetime.now(UTC).isoformat(),
               "label": label.strip()[:80] or "Demo recording", "exercise": plan.exercise,
               "plan": plan.dict(), "symptoms": symptoms[:2000], "reported_pain": pain,
               "synthetic": synthetic, "duration": round(duration, 2), "processing_seconds": round(elapsed, 2),
               "source_video": str(source), "annotated_video": str(annotated), "samples": samples,
               "feedback": "", "model": "Synthetic landmarks — no AI inference" if synthetic else "usyd-community/vitpose-plus-small + PekingU/rtdetr_r18vd",
               "measurement": "Approximate 2D camera-view movement measurements; not calibrated clinical ROM.", **metrics}
    if reference:
        session["reference_curve"] = reference["templates"][plan.primary_feature]["median"]
    storage.save(session)
    return session


def analyse_video(path, plan, label, symptoms, pain, progress=lambda *_: None):
    from .tracking import extract, measured_samples, render_overlay
    started = time.monotonic()
    record = extract(path, plan, progress)
    session_id, directory = storage.new_folder()
    suffix = Path(path).suffix.lower()
    source = directory / ("source" + (suffix if suffix in (".mov", ".mp4", ".avi", ".webm", ".mkv") else ".mp4"))
    shutil.copy2(path, source)
    samples = measured_samples(record, plan)
    reference = storage.load_reference(plan.reference_id) if plan.reference_id else None
    assessment = assess(samples, plan, reference)  # validate before media conversion
    annotated = render_overlay(source, directory / "annotated.mp4", record, samples, progress, flags=assessment["flags"])
    session = finish(session_id, directory, samples, plan, source, annotated, record["duration"], label, symptoms, pain, False, time.monotonic() - started, reference)
    session["inference_provenance"] = {k: record[k] for k in ("pose_model", "detector", "pose_revision", "detector_revision", "cache_hit", "extraction_seconds")}
    session["analysis_fps"] = plan.sample_fps
    storage.save(session)
    progress(1, "Session ready for review.")
    return session


def train_reference(path, plan, label, approved=False, cues=None, progress=lambda *_: None):
    from dataclasses import replace

    from .avatar import render_guide
    reference_plan = replace(plan, reference_id=None)
    session = analyse_video(path, reference_plan, label, "Reference demonstration selected by the team.", None, progress)
    model = fit_reference(session, approved=approved, cues=cues)
    model["label"] = label[:80] or "Reference demonstration"
    model["created_at"] = session["created_at"]
    model_path = storage.save_reference(model)
    guide = render_guide(session, storage.folder(session["id"]) / "motion-guide.mp4")
    session["kind"] = "reference"
    session["guide_video"] = guide
    storage.save(session)
    return session, model, model_path


def example_session(plan):
    from .example import make_example
    return make_example(plan)
