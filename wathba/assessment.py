"""Reference-conditioned motion assessment.

The pose model estimates landmarks. This module fits phase-normalised reference
curves and robust variation, then compares complete observed cycles. It never
equates a deviation from a demonstration with a clinical diagnosis.
"""

import math
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from .motion import interior_angle
from .pose_schema import INDEX as J

# Shoulders, hips and ankles: needed by frontal pelvic descent and jump lift.
BODY_HEIGHT_JOINTS = ("left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_ankle", "right_ankle")


@dataclass(frozen=True)
class Feature:
    name: str
    label: str
    label_ar: str
    unit: str
    min_motion: float
    tolerance: float


FEATURES = {
    "foot_lift": Feature("foot_lift", "Both-foot lift from the initial floor position", "ارتفاع القدمين عن موضع البداية", "torso lengths", .06, .08),
    "knee_angle": Feature("knee_angle", "2D knee interior angle", "زاوية الركبة التقديرية", "deg", 8.0, 12.0),
    "hip_angle": Feature("hip_angle", "2D hip interior angle", "زاوية الورك التقديرية", "deg", 8.0, 15.0),
    "torso_lean": Feature("torso_lean", "Trunk inclination in the camera view", "ميل الجذع في زاوية التصوير", "deg", 6.0, 12.0),
    "leg_elevation": Feature("leg_elevation", "Leg orientation in the camera view", "اتجاه الساق في زاوية التصوير", "deg", 8.0, 12.0),
    "hip_height": Feature("hip_height", "Hip height relative to torso length", "ارتفاع الورك نسبةً إلى طول الجذع", "torso lengths", .08, .12),
    "knee_offset": Feature("knee_offset", "Projected knee offset from hip–ankle line", "انحراف الركبة الظاهر عن خط الورك والكاحل", "leg lengths", .05, .08),
}


def pose_features(points, scores, side, threshold=.45, reliable=None):
    """2D image-plane features from named COCO-17 joints.

    `reliable` is a per-joint mask from the producing model's own threshold. When
    absent (older server-side records), `scores >= threshold` is used. A feature
    is None unless every joint it needs is reliable; nothing is substituted.
    """
    points, scores = np.asarray(points, float), np.asarray(scores, float)
    if points.shape != (17, 2) or scores.shape != (17,):
        raise ValueError("Expected 17 two-dimensional landmarks and scores.")
    ok = np.asarray(reliable, bool) if reliable is not None else (np.isfinite(scores) & (scores >= threshold))
    s = "left" if side == "Left" else "right"
    shoulder, hip, knee, ankle = (J[f"{s}_shoulder"], J[f"{s}_hip"], J[f"{s}_knee"], J[f"{s}_ankle"])
    features, confidence = {}, {}

    def add(name, indices, fn):
        indices = list(indices)
        visible = bool(ok[indices].all()) and bool(np.isfinite(points[indices]).all())
        # Raw model score of the weakest joint, for provenance only; reliability is the gate.
        confidence[name] = round(max(0.0, min(1.0, float(np.min(scores[indices])))), 4) if np.isfinite(scores[indices]).all() else 0.0
        value = fn() if visible else None
        features[name] = round(float(value), 4) if value is not None and math.isfinite(value) else None

    add("knee_angle", (hip, knee, ankle), lambda: interior_angle(points[hip], points[knee], points[ankle]))
    add("hip_angle", (shoulder, hip, knee), lambda: interior_angle(points[shoulder], points[hip], points[knee]))
    add("torso_lean", (shoulder, hip), lambda: math.degrees(math.atan2(abs(points[shoulder, 0] - points[hip, 0]), abs(points[hip, 1] - points[shoulder, 1]))))
    add("leg_elevation", (hip, ankle), lambda: math.degrees(math.atan2(abs(points[ankle, 0] - points[hip, 0]), points[ankle, 1] - points[hip, 1])))

    def height():
        torso = np.linalg.norm((points[J["left_shoulder"]] + points[J["right_shoulder"]] - points[J["left_hip"]] - points[J["right_hip"]]) / 2)
        return ((points[J["left_ankle"], 1] + points[J["right_ankle"], 1] - points[J["left_hip"], 1] - points[J["right_hip"], 1]) / 2) / torso if torso > 5 else None

    add("hip_height", [J[n] for n in BODY_HEIGHT_JOINTS], height)

    def offset():
        axis = points[ankle] - points[hip]
        length = np.linalg.norm(axis)
        if length < 10:
            return None
        rel = points[knee] - points[hip]
        return abs(float(axis[0] * rel[1] - axis[1] * rel[0])) / (length * length)

    add("knee_offset", (hip, knee, ankle), offset)
    return features, confidence


def joints_reliable(sample, names):
    """Per-joint reliability from the producing model; legacy records use score >= .45."""
    mask, scores = sample.get("reliable"), sample.get("scores")
    if sample.get("points") is None:
        return False
    if mask is not None:
        return all(mask[J[n]] for n in names)
    return scores is not None and min(scores[J[n]] for n in names) >= .45


def _xy(sample, name):
    return np.asarray(sample["points"][J[name]], float)


def value(sample, name):
    if name in sample.get("features", {}):
        return sample["features"][name]
    return sample.get("angle") if name == "knee_angle" else None


def normalise_frontal_height(samples):
    """Use one robust body scale per recording, not a torso that foreshortens.

    Dividing by each frame's projected torso length can invert a squat when the
    person leans forward. A static scale preserves the actual pelvic excursion.
    """
    measurements = []
    for i, s in enumerate(samples):
        if not joints_reliable(s, BODY_HEIGHT_JOINTS):
            continue
        torso = float(np.linalg.norm((_xy(s, "left_shoulder") + _xy(s, "right_shoulder") - _xy(s, "left_hip") - _xy(s, "right_hip")) / 2))
        height = float((_xy(s, "left_ankle")[1] + _xy(s, "right_ankle")[1] - _xy(s, "left_hip")[1] - _xy(s, "right_hip")[1]) / 2)
        if torso > 5 and math.isfinite(height):
            measurements.append((i, torso, height))
    if not measurements:
        return samples
    scale = float(np.quantile([r[1] for r in measurements], .75))
    for i, _, height in measurements:
        samples[i]['features']['hip_height'] = round(height/scale, 4)
        samples[i]['body_scale_pixels'] = round(scale, 4)
    return samples


def feature_confidence(sample, name):
    return sample.get("feature_confidence", {}).get(name, sample.get("confidence", 0))


def normalise_jump_height(samples):
    """Fixed-camera, both-foot (ankle) vertical displacement; not force or jump safety."""
    reliable = [s for s in samples if joints_reliable(s, BODY_HEIGHT_JOINTS)]
    if not reliable:
        return samples
    initial = reliable[:max(1, min(6, len(reliable)))]
    floor = float(np.median([max(_xy(s, "left_ankle")[1], _xy(s, "right_ankle")[1]) for s in initial]))
    scale = float(np.quantile([np.linalg.norm((_xy(s, "left_shoulder") + _xy(s, "right_shoulder") - _xy(s, "left_hip") - _xy(s, "right_hip")) / 2) for s in reliable], .75))
    if scale <= 5:
        return samples
    for s in samples:
        ok = joints_reliable(s, BODY_HEIGHT_JOINTS)
        scores = s.get('scores')
        s['feature_confidence']['foot_lift'] = min(scores[J[n]] for n in BODY_HEIGHT_JOINTS) if scores else 0
        s.setdefault('feature_reliable', {})['foot_lift'] = ok
        s['features']['foot_lift'] = round((floor-max(_xy(s, "left_ankle")[1], _xy(s, "right_ankle")[1]))/scale, 4) if ok else None
    return samples


def valid(sample, name):
    v = value(sample, name)
    if v is None or not math.isfinite(v):
        return False
    gate = sample.get("feature_reliable")
    if gate is not None and name in gate:
        return bool(gate[name])
    # Records without per-model reliability (older server-side extraction).
    return feature_confidence(sample, name) >= .45


def runs(samples, name):
    """Split at uncertain frames and unobserved intervals; do not invent continuity."""
    result, current = [], []
    last = None
    for i, sample in enumerate(samples):
        t = sample["time"]
        if last is not None and t <= last:
            raise ValueError("Recording samples must have increasing timestamps.")
        if (not valid(sample, name) or (last is not None and t - last > .8)) and current:
            result.append(current)
            current = []
        if valid(sample, name):
            current.append(i)
        last = t
    if current:
        result.append(current)
    return result


def segment_cycles(samples, name="knee_angle", polarity=None):
    """Detect complete rest→excursion→rest cycles, including smaller excursions."""
    feature = FEATURES[name]
    cycles = []
    for indices in runs(samples, name):
        if len(indices) < 5:
            continue
        t = np.array([samples[i]["time"] for i in indices])
        raw = np.array([value(samples[i], name) for i in indices], dtype=float)
        y = gaussian_filter1d(raw, .55, mode="nearest")
        # Smoothing must not erase an observed return at the recording boundary.
        y[0], y[-1] = raw[0], raw[-1]
        qlo, qhi = np.quantile(y, [.08, .92])
        span = float(qhi - qlo)
        if span < feature.min_motion:
            continue
        dt = float(np.median(np.diff(t)))
        direction = polarity if polarity in (-1, 1) else (1 if abs(y[0] - qlo) <= abs(y[0] - qhi) else -1)
        z = y * direction
        lo = float(np.quantile(z, .08))
        rest_limit = lo + max(feature.min_motion * .20, span * .18)
        peaks, _ = find_peaks(z, prominence=feature.min_motion * .65, distance=max(2, int(.65 / dt)))
        previous_end = -1
        for peak in peaks:
            lefts = np.flatnonzero(z[:peak] <= rest_limit)
            rights = np.flatnonzero(z[peak + 1:] <= rest_limit)
            if not len(lefts) or not len(rights):
                continue  # partial repetitions at either recording edge
            left, right = int(lefts[-1]), int(peak + 1 + rights[0])
            if left < previous_end or t[right] - t[left] < .45:
                continue
            amplitude = float(z[peak] - (z[left] + z[right]) / 2)
            if amplitude < feature.min_motion:
                continue
            section = raw[left:right + 1]
            cycles.append({"rep": len(cycles) + 1, "start": round(float(t[left]), 4), "end": round(float(t[right]), 4),
                           "peak_time": round(float(t[peak]), 4), "duration": round(float(t[right] - t[left]), 4),
                           "minimum": round(float(section.min()), 3), "maximum": round(float(section.max()), 3),
                           "excursion": round(float(section.max() - section.min()), 3),
                           "polarity": direction, "sample_start": indices[left], "sample_end": indices[right]})
            previous_end = right
    return cycles


def waveform(samples, cycle, feature, size=61):
    section = samples[cycle["sample_start"]:cycle["sample_end"] + 1]
    reliable = [s for s in section if valid(s, feature)]
    if len(reliable) < 3 or len(reliable) / len(section) < .8:
        return None
    t = np.array([s["time"] for s in reliable])
    if np.max(np.diff(t)) > .5:
        return None
    phase = (t - cycle["start"]) / cycle["duration"]
    if phase[0] > .15 or phase[-1] < .85:
        return None
    curve = np.interp(np.linspace(0, 1, size), phase, [value(s, feature) for s in reliable])
    # Compare frontal descent from the start position, not different people's
    # absolute leg-to-torso proportions or initial camera-view hip height.
    return curve - curve[0] if feature == "hip_height" else curve


def align_curves(reference, observed, band=.20):
    """Constrained DTW; timing is reported separately rather than hidden by alignment."""
    a, b = np.asarray(reference, float), np.asarray(observed, float)
    n, m = len(a), len(b)
    radius = max(abs(n - m), int(max(n, m) * band))
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0
    previous = {}
    for i in range(1, n + 1):
        for j in range(max(1, i - radius), min(m, i + radius) + 1):
            choices = ((i - 1, j - 1), (i - 1, j), (i, j - 1))
            p = min(choices, key=lambda ij: cost[ij])
            cost[i, j] = abs(a[i - 1] - b[j - 1]) + cost[p]
            previous[(i, j)] = p
    if not np.isfinite(cost[n, m]):
        raise ValueError("Could not align movement curves.")
    path, cursor = [], (n, m)
    while cursor != (0, 0):
        i, j = cursor
        if i and j:
            path.append((i - 1, j - 1))
        cursor = previous[cursor]
    path.reverse()
    return np.array(path, dtype=int)


def fit_reference(session, approved=False, cues=None, tolerance_scale=1.0):
    """Fit a statistical motion model to recorded reference repetitions, not labels."""
    primary = session["plan"].get("primary_feature", "knee_angle")
    cycles = segment_cycles(session["samples"], primary)
    if len(cycles) < 2:
        raise ValueError("A reference needs at least two complete, clearly visible repetitions. Include the start and return of each movement.")
    if not .5 <= tolerance_scale <= 3:
        raise ValueError("Reference tolerance must be between 0.5 and 3.")
    view = session["plan"].get("view", "Side")
    names = [primary, "hip_angle", "torso_lean"] if view == "Side" else [primary, "knee_offset", "torso_lean"]
    templates = {}
    for name in dict.fromkeys(names):
        waves = [w for c in cycles if (w := waveform(session["samples"], c, name)) is not None]
        if len(waves) < 2:
            continue
        matrix = np.stack(waves)
        median = np.median(matrix, axis=0)
        mad = np.median(np.abs(matrix - median), axis=0) * 1.4826
        excursions = np.ptp(matrix, axis=1)
        templates[name] = {"median": median.round(5).tolist(), "spread": mad.round(5).tolist(),
                           "excursion_median": float(np.median(excursions)),
                           "excursion_mad": float(np.median(abs(excursions - np.median(excursions))) * 1.4826),
                           "training_cycles": len(waves), "tolerance": FEATURES[name].tolerance * tolerance_scale}
    if primary not in templates:
        raise ValueError("Reference movement is not visible consistently enough to fit its primary feature.")
    durations = np.array([c["duration"] for c in cycles])
    return {"schema_version": 1, "method": "phase-normalised robust reference model with constrained dynamic time warping",
            "reference_session_id": session["id"], "exercise": session["plan"].get("exercise", session["exercise"]),
            "view": view, "side": session["plan"]["side"], "primary_feature": primary,
            "approved_by_user": bool(approved), "synthetic": bool(session["synthetic"]), "clinical_validation": False,
            "training_cycles": len(cycles), "training_duration_seconds": session["duration"],
            "polarity": cycles[0]["polarity"], "duration_median": float(np.median(durations)),
            "duration_mad": float(np.median(abs(durations - np.median(durations))) * 1.4826),
            "templates": templates, "cues": {k: str(v)[:1000] for k, v in (cues or {}).items()},
            "provenance": "Illustrative synthetic motion; not a clinical reference" if session["synthetic"] else "Pose estimates from the selected reference video"}


def tracking_flags(samples, primary):
    flags, start = [], None
    for i, sample in enumerate(samples):
        if not valid(sample, primary):
            start = sample["time"] if start is None else start
        elif start is not None:
            if sample["time"] - start >= .4:
                flags.append({"kind": "tracking", "start": start, "end": sample["time"], "title": "Movement was not visible reliably",
                              "detail": "The required landmarks were uncertain. No movement correction is inferred across this interval.",
                              "cue": "Keep the selected person and required joints in view, then record again.", "evidence": []})
            start = None
        if i and sample["time"] - samples[i - 1]["time"] > .8:
            flags.append({"kind": "tracking", "start": samples[i - 1]["time"], "end": sample["time"], "title": "Recording samples were interrupted",
                          "detail": "No continuous movement was observed in this interval.", "cue": "Review the recording quality.", "evidence": []})
    if start is not None and samples[-1]["time"] - start >= .4:
        flags.append({"kind": "tracking", "start": start, "end": samples[-1]["time"], "title": "Movement visibility was lost",
                      "detail": "Recording ended with uncertain landmarks.", "cue": "Keep the required joints visible.", "evidence": []})
    return flags


def cycle_matches_reference(cycle, samples, reference, coverage, primary):
    """Keep observed motion separate from an assessable, matched repetition."""
    if not reference or coverage < 70 or cycle.get("findings"):
        return False
    required = list(reference["templates"])
    if primary == "hip_height":
        required.append("knee_angle")
    return all(waveform(samples, cycle, name) is not None for name in required)


def assess(samples, plan, reference=None, illustrative=False):
    primary = plan.primary_feature
    observed = [float(value(s, primary)) for s in samples if valid(s, primary)]
    if not observed:
        raise ValueError("No reliable movement tracking. Choose the correct leg and camera view, and keep the required joints visible.")
    if reference:
        if (reference["exercise"] != plan.exercise or reference["view"] != plan.view or
                reference["primary_feature"] != primary or reference["side"] != plan.side):
            raise ValueError("The selected reference must match the exercise, tracked leg, camera view, and measured movement. Fit an appropriate demonstration for this leg before comparing.")
        if reference["synthetic"] and not (illustrative or plan.allow_illustrative_reference):
            raise ValueError("An illustrative synthetic guide cannot be used to judge a real patient's exercise. Select a recorded reference.")
    cycles = segment_cycles(samples, primary, reference.get("polarity") if reference else None)
    flags = tracking_flags(samples, primary)
    if reference and not cycles:
        flags.append({"kind": "assessment", "start": samples[0]["time"], "end": min(samples[-1]["time"], samples[0]["time"] + 5),
                      "title": "The reference movement could not be assessed",
                      "detail": "No complete movement cycle was visible for the selected reference. This recording cannot establish whether the exercise matched the assigned movement.",
                      "cue": "Check the selected exercise, leg, camera view, and whether the video includes complete repetitions.", "evidence": []})
    for cycle in cycles:
        findings = []
        if reference and len(observed)/len(samples) >= .70:
            duration_allowance = max(reference["duration_mad"] * 3, reference["duration_median"] * .25, .35)
            expected = reference["duration_median"]
            if abs(cycle["duration"] - expected) > duration_allowance:
                findings.append({"kind": "pace", "feature": "duration", "observed": cycle["duration"], "reference": round(expected, 3), "unit": "s",
                                 "tolerance": round(duration_allowance, 3), "part": "Timing", "time": cycle['peak_time'],
                                 "severity": "red" if abs(cycle['duration']-expected)>2*duration_allowance else "yellow",
                                 "description": f"This repetition was {'faster' if cycle['duration'] < expected else 'slower'} than the selected reference: {cycle['duration']:.2f}s versus {expected:.2f}s (tolerance ±{duration_allowance:.2f}s)."})
            for name, template in reference["templates"].items():
                wave = waveform(samples, cycle, name)
                if wave is None:
                    continue
                ref_wave = np.array(template["median"])
                path = align_curves(ref_wave, wave)
                delta = abs(ref_wave[path[:, 0]] - wave[path[:, 1]])
                allowed = np.maximum(np.array(template["spread"])[path[:, 0]] * 3, template["tolerance"])
                fraction = float(np.mean(delta > allowed))
                kind = "pattern"
                description = f"{FEATURES[name].label} differs from the selected reference across {fraction:.0%} of aligned observations."
                if name == primary:
                    range_allowance = max(template["excursion_mad"] * 3, template["tolerance"])
                    if abs(np.ptp(wave) - template["excursion_median"]) > range_allowance:
                        kind = "range"
                        description = f"This repetition had a {'smaller' if np.ptp(wave) < template['excursion_median'] else 'larger'} observed movement excursion than the selected reference: {np.ptp(wave):.3f} versus {template['excursion_median']:.3f} {FEATURES[name].unit} (tolerance ±{range_allowance:.3f})."
                        findings.append({"kind": kind, "feature": name, "observed": round(float(np.ptp(wave)), 3),
                                         "reference": round(template["excursion_median"], 3), "unit": FEATURES[name].unit,
                                         "part": "Legs / pelvis", "time": cycle['peak_time'], "tolerance": round(range_allowance,4),
                                         "severity": "red" if abs(np.ptp(wave)-template['excursion_median'])>2*range_allowance else "yellow",
                                         "description": description})
                        continue
                if fraction >= .25:
                    worst = int(np.argmax(delta / np.maximum(allowed, .0001)))
                    findings.append({"kind": kind, "feature": name, "observed": round(float(np.mean(delta)), 3),
                                     "reference": round(float(np.mean(allowed)), 3), "unit": FEATURES[name].unit,
                                     "tolerance": round(float(np.mean(allowed)),4),
                                     "part": "Trunk" if name=='torso_lean' else "Left knee" if name=='knee_offset' else "Legs / pelvis",
                                     "time": round(cycle['start']+float(path[worst,1])/(len(wave)-1)*cycle['duration'],4),
                                     "reference_phase": round(float(path[worst,0])/(len(ref_wave)-1),4),
                                     "peak_difference": round(float(delta[worst]),4), "outside_tolerance_pct": round(fraction*100,1),
                                     "severity": "red" if float(np.mean(delta/np.maximum(allowed,.0001)))>2 else "yellow",
                                     "description": description})
        cycle["findings"] = findings
        # A detected cycle is not automatically a matched repetition. Missing
        # comparison features must never turn into a false success.
        required = list(reference["templates"]) if reference else []
        assessable = bool(reference and len(observed) / len(samples) >= .70 and
                          all(waveform(samples, cycle, name) is not None for name in required))
        if primary == "hip_height":
            assessable = assessable and waveform(samples, cycle, "knee_angle") is not None
        cycle["accepted"] = cycle_matches_reference(cycle, samples, reference, 100 * len(observed) / len(samples), primary)
        cycle["comparison_assessable"] = bool(assessable)
        if findings:
            cue_text = []
            for finding in findings:
                configured = reference["cues"].get(finding["kind"], "")
                if configured and reference["approved_by_user"]:
                    cue_text.append(configured)
            flags.append({"kind": findings[0]["kind"], "start": cycle["start"], "end": cycle["end"], "rep": cycle["rep"],
                          "title": f"Repetition {cycle['rep']}: {', '.join(dict.fromkeys(f['part'] for f in findings))}", "detail": " ".join(f["description"] for f in findings),
                          "severity": "red" if any(f['severity']=='red' for f in findings) else "yellow",
                          "cue": " ".join(dict.fromkeys(cue_text)) or "Compare this clip with your assigned reference and ask your physiotherapist about the difference.",
                          "evidence": findings, "cue_source": "User-confirmed physiotherapist cue" if cue_text else "Reference comparison; clinician interpretation required"})
    flags.sort(key=lambda f: (f["start"], f["end"]))
    for i, flag in enumerate(flags):
        flag.update(id=f"flag-{i + 1}", status="Pending", comment="")
    knee_angles = [value(s, "knee_angle") for s in samples if valid(s, "knee_angle")]
    return {"repetitions": len(cycles), "accepted_repetitions": sum(c["accepted"] for c in cycles),
            "cycles": cycles, "flags": flags, "primary_feature": primary,
            "feature_label": FEATURES[primary].label, "feature_unit": FEATURES[primary].unit,
            "coverage": round(100 * len(observed) / len(samples), 1),
            "angle_min": round(min(knee_angles), 1) if knee_angles else None,
            "angle_max": round(max(knee_angles), 1) if knee_angles else None,
            "measurement_min": round(min(observed), 3), "measurement_max": round(max(observed), 3),
            "median_cycle_seconds": round(float(np.median([c["duration"] for c in cycles])), 3) if cycles else None,
            "assessment_status": ("Illustrative reference comparison" if reference["synthetic"] else "Reference comparison") if reference else "Measurements only — no comparison reference selected",
            "reference_model": {k: reference[k] for k in ("reference_session_id", "exercise", "view", "training_cycles", "approved_by_user", "method", "synthetic")} if reference else None,
            "limitations": ["2D image-plane measurements are approximate and depend on camera placement; no depth is estimated.",
                            "A difference from a reference is not, by itself, proof of incorrect or unsafe exercise."] +
                           (["The selected reference is an illustrated research motion, not a patient-specific clinical standard."] if reference and reference["synthetic"] else []) +
                           ([] if reference else ["No reference was selected; exercise correctness and corrective movement cues were not inferred."]) +
                           (["No complete repetitions were visible; partial movements were not counted."] if not cycles else [])}
