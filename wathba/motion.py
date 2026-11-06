"""Transparent motion measurements and review prompts, independent of inference."""

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Plan:
    lower_angle: float = 95.0
    upper_angle: float = 145.0
    min_cycle_seconds: float = 2.0
    target_repetitions: int = 5
    side: str = "Left"
    exercise: str = "Squat"
    view: str = "Side"
    primary_feature: str = "knee_angle"
    segmentation: str = "adaptive"
    sample_fps: int = 6
    reference_id: str | None = None
    subject_roi: tuple | None = None
    allow_illustrative_reference: bool = False

    def __post_init__(self):
        if not 20 <= self.lower_angle < self.upper_angle <= 175:
            raise ValueError("Use ordered thresholds between 20 and 175 degrees.")
        if self.upper_angle - self.lower_angle < 15:
            raise ValueError("Thresholds must be at least 15 degrees apart.")
        if not 0.5 <= self.min_cycle_seconds <= 20:
            raise ValueError("Cycle duration must be between 0.5 and 20 seconds.")
        if not 1 <= self.target_repetitions <= 50:
            raise ValueError("Choose 1 to 50 target repetitions.")
        if self.side not in ("Left", "Right"):
            raise ValueError("Choose Left or Right.")
        if self.view not in ("Side", "Front"):
            raise ValueError("Choose a side or front view.")
        if self.primary_feature not in ("knee_angle", "leg_elevation", "hip_height", "foot_lift"):
            raise ValueError("Unsupported movement feature.")
        if self.segmentation not in ("adaptive", "manual"):
            raise ValueError("Unknown segmentation method.")
        if not 3 <= self.sample_fps <= 12:
            raise ValueError("Use 3 to 12 analysis frames per second.")
        if not self.exercise.strip() or len(self.exercise) > 100:
            raise ValueError("Enter an exercise name of 1 to 100 characters.")
        if self.subject_roi is not None:
            if len(self.subject_roi) != 4 or not all(math.isfinite(float(v)) and 0 <= v <= 1 for v in self.subject_roi):
                raise ValueError("Subject region must contain four normalised coordinates.")
            x1, y1, x2, y2 = self.subject_roi
            if x2 - x1 < .05 or y2 - y1 < .05:
                raise ValueError("Choose a subject region at least 5% of the frame in each direction.")

    def dict(self):
        return asdict(self)


def interior_angle(a, b, c):
    u = (a[0] - b[0], a[1] - b[1])
    v = (c[0] - b[0], c[1] - b[1])
    denom = math.hypot(*u) * math.hypot(*v)
    if denom < 1e-6:
        return None
    return math.degrees(math.acos(max(-1, min(1, (u[0] * v[0] + u[1] * v[1]) / denom))))


def measure_keypoints(points, scores, side, threshold=0.45):
    indices = (11, 13, 15) if side == "Left" else (12, 14, 16)
    confidence = min(float(scores[i]) for i in indices)
    if not math.isfinite(confidence):
        confidence = 0.0
    valid = confidence >= threshold
    if any(not all(math.isfinite(float(v)) for v in points[i]) for i in indices):
        valid = False
    angle = interior_angle(*(points[i] for i in indices)) if valid else None
    return angle, round(confidence, 3)


def analyse_trace(samples, plan):
    """Count complete low→high→low cycles; never bridge uncertain observations."""
    cycles, flags = [], []
    phase, start, last_t = "waiting", None, None
    gap_start = None
    for sample in samples:
        t, angle = float(sample["time"]), sample.get("angle")
        if last_t is not None and t <= last_t:
            raise ValueError("Samples must have increasing timestamps.")
        missing_interval = last_t is not None and t - last_t > 0.8
        valid = angle is not None and math.isfinite(angle) and sample.get("confidence", 0) >= 0.45
        if missing_interval:
            flags.append({"kind": "tracking", "start": last_t, "end": t,
                          "title": "Tracking interrupted", "detail": "No continuous observation across this interval. Cycle counting restarted."})
            phase, start = "waiting", None
        if not valid:
            if gap_start is None:
                gap_start = t
            phase, start = "waiting", None
            last_t = t
            continue
        if gap_start is not None:
            if t - gap_start >= 0.5:
                flags.append({"kind": "tracking", "start": gap_start, "end": t,
                              "title": "View needs review", "detail": "Hip, knee, or ankle tracking was uncertain. Movement could not be assessed here."})
            gap_start = None
        if angle <= plan.lower_angle:
            if phase == "high":
                duration = t - start
                cycle = {"rep": len(cycles) + 1, "start": round(start, 3), "end": round(t, 3), "duration": round(duration, 3)}
                cycles.append(cycle)
                if duration < plan.min_cycle_seconds:
                    flags.append({"kind": "pace", "start": start, "end": t, "rep": cycle["rep"],
                                  "title": f"Review pace · repetition {cycle['rep']}",
                                  "detail": f"Observed cycle {duration:.1f}s; configured minimum {plan.min_cycle_seconds:.1f}s. Clinician review required."})
                phase, start = "low", t
            elif phase == "waiting":
                phase, start = "low", t
        elif angle >= plan.upper_angle and phase == "low":
            phase = "high"
        last_t = t
    if gap_start is not None and last_t - gap_start >= 0.5:
        flags.append({"kind": "tracking", "start": gap_start, "end": last_t,
                      "title": "View needs review", "detail": "Recording ends with uncertain tracking. No complete movement was inferred."})
    valid_samples = [s for s in samples if s.get("angle") is not None and s.get("confidence", 0) >= 0.45 and math.isfinite(s["angle"])]
    if not valid_samples:
        raise ValueError("No reliable hip–knee–ankle tracking. Use one person, a steady side view, and keep the whole leg visible.")
    flags.sort(key=lambda f: (f["start"], f["end"]))
    for i, flag in enumerate(flags):
        flag.update(id=f"flag-{i + 1}", status="Pending", comment="")
    return {"repetitions": len(cycles), "cycles": cycles, "flags": flags,
            "coverage": round(100 * len(valid_samples) / len(samples), 1),
            "angle_min": round(min(s["angle"] for s in valid_samples), 1),
            "angle_max": round(max(s["angle"] for s in valid_samples), 1)}
