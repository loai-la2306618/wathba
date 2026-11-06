"""Synthetic squat illustration and explicitly labelled research comparison guide."""

import math
from dataclasses import replace

import cv2
import numpy as np

from . import storage
from .assessment import fit_reference, pose_features
from .avatar import draw_human, render_guide
from .media import draw_pose, encode_mp4


def make_example(plan, reference_only=False):
    from .pipeline import finish
    plan = replace(plan, exercise="Squat", side="Left", primary_feature="hip_height" if plan.view == "Front" else "knee_angle", reference_id=None)
    session_id, directory = storage.new_folder()
    fps, durations = 12, ([3.4, 3.4, 3.4] if reference_only else [3.4, 3.4, 1.2, 3.4, 3.4])
    total = sum(durations) + (0 if reference_only else 1)
    samples = []
    raw_source, raw_overlay = directory / "source-raw.mp4", directory / "overlay-raw.mp4"
    source_writer = cv2.VideoWriter(str(raw_source), cv2.VideoWriter_fourcc(*"mp4v"), fps, (800, 520))
    overlay_writer = cv2.VideoWriter(str(raw_overlay), cv2.VideoWriter_fourcc(*"mp4v"), fps, (800, 520))
    for i in range(round(total * fps)):
        t, elapsed = i / fps, 0
        phase, rep = 0, 0
        for rep, duration in enumerate(durations):
            if t <= elapsed + duration:
                phase = (t - elapsed) / duration
                break
            elapsed += duration
        bend = (1 - math.cos(2 * math.pi * phase)) / 2 if t < sum(durations) else 0
        excursion = (42 if rep == 3 and not reference_only else 80) * bend
        interior = 175 - excursion
        alpha = math.radians((180 - interior) * .35)
        beta = math.radians((180 - interior) * .65)
        ankle = np.array([430., 455.])
        knee = ankle + np.array([115 * math.sin(alpha), -115 * math.cos(alpha)])
        hip = knee + np.array([-115 * math.sin(beta), -115 * math.cos(beta)])
        lean = math.radians(10 + 15 * bend)
        shoulder = hip + np.array([115 * math.sin(lean), -115 * math.cos(lean)])
        points = np.zeros((17, 2), float)
        for offset, indices in [(np.array([0., 0.]), (5, 7, 9, 11, 13, 15)), (np.array([-26., 2.]), (6, 8, 10, 12, 14, 16))]:
            sh, el, wr, hi, kn, an = indices
            points[sh], points[hi], points[kn], points[an] = shoulder + offset, hip + offset, knee + offset, ankle + offset
            points[el] = shoulder + offset + np.array([54., 28.])
            points[wr] = shoulder + offset + np.array([95., 25.])
        points[:5] = shoulder + np.array([6., -39.])
        if plan.view == "Front":
            # Original frontal illustration: pelvic descent is visible; sagittal
            # knee flexion cannot be inferred accurately from this view.
            drop = (42 if rep == 3 and not reference_only else 80) * bend
            for sh, el, wr, hi, kn, an, direction in [(5,7,9,11,13,15,-1),(6,8,10,12,14,16,1)]:
                points[hi] = [400 + direction * 35, 260 + drop]
                points[sh] = [400 + direction * 43, 145 + drop]
                points[kn] = [400 + direction * (45 + 12 * bend), 355 + 9 * bend]
                points[an] = [400 + direction * 55, 455]
                points[el] = [400 + direction * 72, 202 + drop]
                points[wr] = [400 + direction * 8, 188 + drop]
            points[:5] = [400, 106 + drop]
        scores = np.full(17, .97)
        frame, projected = draw_human(points, scores, plan.side, return_points=True)
        cv2.putText(frame, "SYNTHETIC SQUAT EXAMPLE - NOT PATIENT FOOTAGE", (26, 57), cv2.FONT_HERSHEY_SIMPLEX, .44, (95, 77, 55), 1, cv2.LINE_AA)
        if not reference_only and sum(durations) + .1 < t < total:
            scores[[11, 13, 15, 12, 14, 16]] = .2
            cv2.rectangle(frame, (300, 335), (510, 470), (196, 204, 208), -1)
            cv2.putText(frame, "Illustrated occlusion", (318, 392), cv2.FONT_HERSHEY_SIMPLEX, .5, (90, 75, 60), 1, cv2.LINE_AA)
        features, feature_conf = pose_features(projected, scores, plan.side)
        source_writer.write(frame)
        overlay_writer.write(draw_pose(frame, projected, scores, features["knee_angle"], t, synthetic=True,
                                       caption=f"Hip height: {features['hip_height']:.2f}" if plan.view == "Front" and features["hip_height"] is not None else None))
        if i % 2 == 0:
            samples.append({"time": round(t, 4), "angle": features["knee_angle"], "confidence": feature_conf[plan.primary_feature],
                            "features": features, "feature_confidence": feature_conf, "points": np.round(projected, 3).tolist(), "scores": scores.tolist()})
    source_writer.release()
    overlay_writer.release()
    source = encode_mp4(raw_source, directory / "source.mp4")
    annotated = encode_mp4(raw_overlay, directory / "annotated.mp4")
    reference_source = {"id": session_id, "plan": plan.dict(), "exercise": plan.exercise,
                        "samples": [s for s in samples if s["time"] <= 6.7], "duration": 6.7, "synthetic": True}
    model = fit_reference(reference_source)
    session = finish(session_id, directory, samples, plan, source, annotated, total, "Illustrative squat session",
                     "Synthetic animation with an intentionally faster and smaller-excursion repetition. No patient footage or clinical labels.",
                     None, True, 0, model)
    session["guide_video"] = render_guide(session, directory / "motion-guide.mp4")
    storage.save(session)
    return session


def ensure_illustrative_reference(view="Side"):
    """An inspectable animated comparison asset, with its synthetic provenance intact."""
    from .motion import Plan
    for model in storage.references():
        if model.get("builtin") == f"squat-left-{view.lower()}-v1":
            return model, storage.load(model["reference_session_id"])
    session = make_example(Plan(exercise="Squat", side="Left", view=view), reference_only=True)
    model = fit_reference(session)
    model.update(builtin=f"squat-left-{view.lower()}-v1", label=f"Illustrated squat guide · {view.lower()} view", created_at=session["created_at"])
    session.update(kind="reference", label=model["label"])
    storage.save_reference(model)
    storage.save(session)
    return model, session
