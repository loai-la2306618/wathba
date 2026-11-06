"""Reusable pose extraction and smooth video overlays. Cached locally by content."""

import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np

from . import storage
from .assessment import pose_features, normalise_frontal_height
from .inference import DETECTOR_ID, POSE_ID, PoseTracker, models
from .media import draw_pose, encode_mp4, open_video


def cache_key(path, plan):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    digest.update(json.dumps({"schema": 3, "models": [POSE_ID, DETECTOR_ID], "fps": plan.sample_fps, "roi": plan.subject_roi}, sort_keys=True).encode())
    return digest.hexdigest()


def extract(path, plan, progress=lambda *_: None):
    start = time.monotonic()
    cap, fps, duration = open_video(path)
    key = cache_key(path, plan)
    cache = storage.root() / "pose-cache"
    cache.mkdir(exist_ok=True)
    stored = cache / f"{key}.json"
    if stored.is_file():
        cap.release()
        record = json.loads(stored.read_text())
        record["cache_hit"] = True
        return record
    tracker = PoseTracker(plan.subject_roi)
    rows = []
    stride = max(1, round(fps / plan.sample_fps))
    index = 0
    last_frame = None
    width, height = 0, 0

    def process_frame(frame, t):
        scale = min(1, 960 / max(frame.shape[:2]))
        w = max(2, int(frame.shape[1] * scale) // 2 * 2)
        h = max(2, int(frame.shape[0] * scale) // 2 * 2)
        frame = cv2.resize(frame, (w, h))
        result = tracker.update(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), t)
        points, scores = result if result is not None else (None, None)
        rows.append({"time": round(t, 5), "points": np.round(points, 3).tolist() if points is not None else None,
                     "scores": np.round(scores, 4).tolist() if scores is not None else None,
                     "reason": tracker.reason if points is None else "", "people_detected": tracker.people})
        return w, h
    try:
        progress(.02, "Loading the pose model on this machine.")
        _, _, _, pose_model, _, detector = models()
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            last_frame = frame
            if index % stride == 0:
                t = index / fps
                if t > 180.1:
                    raise ValueError("Recording exceeds the three-minute analysis limit.")
                width, height = process_frame(frame, t)
                progress(min(.85, .05 + .8 * t / duration), f"Tracking the selected person · {t:.0f} / {duration:.0f}s")
            index += 1
        if last_frame is not None and rows and (index - 1) / fps - rows[-1]["time"] > .001:
            width, height = process_frame(last_frame, (index - 1) / fps)
    finally:
        cap.release()
    if not rows:
        raise ValueError("No readable video frames were found.")
    record = {"schema": 3, "rows": rows, "fps": fps, "duration": duration, "width": width, "height": height,
              "pose_model": POSE_ID, "detector": DETECTOR_ID,
              "pose_revision": getattr(pose_model.config, "_commit_hash", None),
              "detector_revision": getattr(detector.config, "_commit_hash", None),
              "extraction_seconds": round(time.monotonic() - start, 3), "cache_hit": False}
    temp = stored.with_suffix(".tmp")
    temp.write_text(json.dumps(record, allow_nan=False))
    temp.replace(stored)
    return record


def measured_samples(record, plan):
    samples = []
    for row in record["rows"]:
        points, scores = row["points"], row["scores"]
        if points is None:
            features, confidence = {}, {}
        else:
            features, confidence = pose_features(points, scores, plan.side)
        samples.append({"time": row["time"], "angle": features.get("knee_angle"),
                        "confidence": confidence.get(plan.primary_feature, 0),
                        "features": features, "feature_confidence": confidence,
                        "primary_feature": plan.primary_feature,
                        "points": points, "scores": scores, "tracking_reason": row.get("reason", "")})
    return normalise_frontal_height(samples) if plan.view == 'Front' else samples


def render_overlay(source, output, record, samples, progress=lambda *_: None, flags=None, reference=None):
    """Retain source motion at up to 24 fps; interpolate only the displayed overlay."""
    cap, source_fps, _duration = open_video(source)
    stride = max(1, round(source_fps / 24))
    fps = source_fps / stride
    raw = Path(output).with_name("overlay-raw.mp4")
    size = (record["width"], record["height"])
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not writer.isOpened():
        cap.release()
        raise ValueError("Could not create the annotated video.")
    i, cursor = 0, 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = i / source_fps
            if i % stride == 0:
                while cursor + 1 < len(samples) and samples[cursor + 1]["time"] <= t:
                    cursor += 1
                s = samples[cursor]
                points, scores = s["points"], s["scores"]
                if cursor + 1 < len(samples):
                    following = samples[cursor + 1]
                    delta = following["time"] - s["time"]
                    if points is not None and following["points"] is not None and delta <= .4:
                        alpha = min(1, max(0, (t - s["time"]) / delta))
                        points = (np.array(points) * (1 - alpha) + np.array(following["points"]) * alpha).tolist()
                        scores = np.minimum(scores, following["scores"]).tolist()
                frame = cv2.resize(frame, size)
                primary = s.get("primary_feature", "knee_angle")
                v = s["features"].get(primary)
                caption = ("Tracking uncertain" if v is None else f"Hip height: {v:.2f}") if primary == "hip_height" else None
                review = any(f["start"] <= t <= f["end"] and f["kind"] not in ("tracking", "assessment") for f in (flags or []))
                parts = {'left':'grey','right':'grey','trunk':'grey'}
                if reference and s.get('confidence',0)>=.45:
                    parts.update(left='green',trunk='green')
                for flag in flags or []:
                    if flag['start'] <= t <= flag['end']:
                        for finding in flag.get('evidence',[]):
                            part = 'trunk' if finding['feature']=='torso_lean' else 'left' if finding['feature']=='knee_offset' else None
                            if part:parts[part]=finding.get('severity','yellow')
                            elif finding['kind']=='range':parts.update(left=finding.get('severity','yellow'),right=finding.get('severity','yellow'))
                writer.write(draw_pose(frame, points, scores, s["angle"], t, caption=caption, review=review, parts=parts))
            i += 1
    finally:
        writer.release()
        cap.release()
    progress(.93, "Encoding the movement overlay.")
    return encode_mp4(raw, output)
