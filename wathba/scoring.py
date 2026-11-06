"""Transparent reference similarity, not a clinical correctness/recovery score."""

import math

import numpy as np

from .assessment import align_curves, waveform


def reference_match(samples, cycles, reference, coverage):
    if not reference or not cycles or coverage < 70:
        return {"value": None, "label": "Reference match", "reason": "A reference, complete repetitions and clear tracking are needed.",
                "clinical_score": False}
    rep_scores = []
    for cycle in cycles:
        feature_scores, weights = [], []
        for name, template in reference["templates"].items():
            observed = waveform(samples, cycle, name)
            if observed is None:
                continue
            expected = np.asarray(template["median"])
            path = align_curves(expected, observed)
            tolerance = np.maximum(3 * np.asarray(template["spread"])[path[:, 0]], template["tolerance"])
            error = float(np.mean(abs(expected[path[:, 0]] - observed[path[:, 1]]) / tolerance))
            feature_scores.append(100 * math.exp(-error))
            weights.append(2 if name == reference["primary_feature"] else 1)
        if not feature_scores:
            continue
        shape = float(np.average(feature_scores, weights=weights))
        # Tempo agreement is separate from time-warped shape agreement.
        tempo = 100 * math.exp(-abs(math.log(cycle["duration"] / reference["duration_median"])))
        rep_scores.append({"rep": cycle["rep"], "value": round(.8 * shape + .2 * tempo)})
    value = round(float(np.mean([r["value"] for r in rep_scores]))) if rep_scores else None
    return {"value": value, "label": "Reference match", "per_repetition": rep_scores, "clinical_score": False,
            "synthetic_reference": reference["synthetic"], "reference_approved_by_user": reference["approved_by_user"],
            "method": "80% tolerance-normalised aligned movement similarity + 20% tempo similarity; mean across assessable repetitions",
            "reason": "Prototype similarity to the selected demonstration, not exercise safety, rehabilitation progress or a diagnosis."}
