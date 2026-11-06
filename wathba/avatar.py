"""A shaded human movement illustration driven by recorded 2D landmarks.

This is our own procedural artwork, not a third-party training asset. It does not
estimate anatomy, muscle activation, or camera depth.
"""

import math
from pathlib import Path

import cv2
import numpy as np

from .media import encode_mp4


def capsule(image, a, b, width, color, taper=.75):
    a, b = np.asarray(a, float), np.asarray(b, float)
    direction = b - a
    length = np.linalg.norm(direction)
    if length < 1:
        return
    normal = np.array([-direction[1], direction[0]]) / length
    # Concentric offset strips create a shaded rounded limb instead of a stick skeleton.
    for k in range(max(2, int(width)), 0, -1):
        ratio = k / width
        brightness = .55 + .45 * math.sqrt(max(0, 1 - ratio * ratio))
        shade = tuple(int(min(255, c * brightness)) for c in color)
        start = a + normal * (width - k) * .14
        end = b + normal * (width - k) * .14
        polygon = np.array([start + normal * k, end + normal * k * taper,
                            end - normal * k * taper, start - normal * k], np.int32)
        cv2.fillConvexPoly(image, polygon, shade, cv2.LINE_AA)
        cv2.circle(image, tuple(start.astype(int)), max(1, k), shade, -1, cv2.LINE_AA)
        cv2.circle(image, tuple(end.astype(int)), max(1, int(k * taper)), shade, -1, cv2.LINE_AA)


def draw_human(points, scores, side, width=800, height=520, return_points=False):
    frame = np.full((height, width, 3), (249, 247, 242), np.uint8)
    p = np.asarray(points, float)
    scores = np.asarray(scores, float)
    valid = np.isfinite(p).all(axis=1) & (scores >= .45)
    if np.count_nonzero(valid) < 8:
        cv2.putText(frame, "Reference joints are not visible here", (120, 250), cv2.FONT_HERSHEY_SIMPLEX, .7, (90, 75, 60), 1, cv2.LINE_AA)
        return (frame, p) if return_points else frame
    p = p.copy()
    visible = p[valid]
    span = max(1, float(np.ptp(visible[:, 1])))
    scale = min((height - 135) / span, (width - 180) / max(1, float(np.ptp(visible[:, 0]))))
    centre = np.mean([p[11], p[12]], axis=0)
    p = (p - centre) * scale + np.array([width / 2, height * .53])
    bottom = float(p[valid, 1].max())
    p[:, 1] += height - 60 - bottom
    torso_length = max(45, float(np.linalg.norm((p[5] + p[6] - p[11] - p[12]) / 2)))
    thickness = min(1.5, max(.7, torso_length / 125))
    cv2.ellipse(frame, (round(float(np.mean(p[[15, 16], 0]))), height - 46), (100, 12), 0, 0, 360, (229, 225, 215), -1, cv2.LINE_AA)
    base, far, accent = (227, 224, 215), (182, 184, 180), (190, 166, 96)
    tracked = (12, 14, 16) if side == "Right" else (11, 13, 15)
    for shoulder, elbow, wrist, hip, knee, ankle in [(5, 7, 9, 11, 13, 15), (6, 8, 10, 12, 14, 16)]:
        colour = accent if hip in tracked else far
        for a, b, radius in [(hip, knee, 18), (knee, ankle, 12), (shoulder, elbow, 10), (elbow, wrist, 8)]:
            if valid[a] and valid[b]:
                capsule(frame, p[a], p[b], radius * thickness, colour if a in (hip, knee) else far)
        if valid[ankle]:
            cv2.ellipse(frame, (int(p[ankle, 0] + 9), int(p[ankle, 1] + 5)), (22, 8), -5, 0, 360, colour, -1, cv2.LINE_AA)
        if valid[wrist]:
            cv2.ellipse(frame, tuple(p[wrist].astype(int)), (8, 12), -15, 0, 360, far, -1, cv2.LINE_AA)
    shoulders = (p[5] + p[6]) / 2
    hips = (p[11] + p[12]) / 2
    capsule(frame, hips, shoulders, 27 * thickness, base, taper=1.15)
    # Subtle torso contours convey a human form without claiming anatomical measurement.
    direction = shoulders - hips
    length = max(1, float(np.linalg.norm(direction)))
    normal = np.array([-direction[1], direction[0]]) / length
    for sign in (-1, 1):
        centre_chest = shoulders * .68 + hips * .32 + normal * sign * 11 * thickness
        cv2.ellipse(frame, tuple(centre_chest.astype(int)), (round(13 * thickness), round(23 * thickness)),
                    -math.degrees(math.atan2(direction[0], -direction[1])), 0, 360, (216, 215, 208), 1, cv2.LINE_AA)
    if valid[0]:
        head = p[0] - np.array([0, 9 * thickness])
    else:
        head = shoulders + direction / length * 40 * thickness
    capsule(frame, shoulders, head + np.array([0, 20 * thickness]), 9 * thickness, base)
    for r in range(round(24 * thickness), 0, -1):
        lum = .6 + .4 * math.sqrt(max(0, 1 - (r / (24 * thickness + 1)) ** 2))
        shade = tuple(round(c * lum) for c in base)
        cv2.ellipse(frame, tuple(head.astype(int)), (r, round(r * 1.22)), 0, 0, 360, shade, -1, cv2.LINE_AA)
    cv2.putText(frame, "WATHBA / MOVEMENT GUIDE", (26, 33), cv2.FONT_HERSHEY_SIMPLEX, .62, (67, 53, 25), 1, cv2.LINE_AA)
    cv2.putText(frame, "Illustrated from 2D joint tracks; not measured 3D anatomy", (26, height - 18), cv2.FONT_HERSHEY_SIMPLEX, .44, (105, 90, 70), 1, cv2.LINE_AA)
    return (frame, p) if return_points else frame


def render_guide(session, output):
    cycles = session["cycles"]
    if not cycles:
        raise ValueError("The motion guide needs a complete recorded repetition.")
    # Use a representative full cycle, keeping the recorded motion intact.
    cycle = min(cycles, key=lambda c: abs(c["duration"] - session["median_cycle_seconds"]))
    samples = session["samples"][cycle["sample_start"]:cycle["sample_end"] + 1]
    usable = [s for s in samples if s.get("points") is not None]
    if len(usable) < 3:
        raise ValueError("Reference landmarks are not available to animate.")
    fps = 24
    raw = Path(output).with_name("guide-raw.mp4")
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (800, 520))
    if not writer.isOpened():
        raise ValueError("Could not create the movement guide.")
    timestamps = np.array([s["time"] for s in usable])
    try:
        for t in np.linspace(cycle["start"], cycle["end"], max(24, round(cycle["duration"] * fps))):
            i = min(len(usable) - 2, max(0, int(np.searchsorted(timestamps, t) - 1)))
            a, b = usable[i], usable[i + 1]
            alpha = min(1, max(0, (t - a["time"]) / (b["time"] - a["time"])))
            points = np.array(a["points"]) * (1 - alpha) + np.array(b["points"]) * alpha
            scores = np.minimum(a["scores"], b["scores"])
            writer.write(draw_human(points, scores, session["plan"]["side"]))
    finally:
        writer.release()
    return encode_mp4(raw, output)
