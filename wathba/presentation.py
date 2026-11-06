"""Grounded bilingual presentation of movement observations and evidence."""

import html

import numpy as np
import pandas as pd

from .assessment import FEATURES, value


def metrics_html(s):
    cards = [(str(s["repetitions"]), "Observed repetitions · تكرارات مرصودة"),
             (f"{s['coverage']:.0f}%", "Trackable samples · وضوح التتبّع"),
             (str(len(s["flags"])), "Moments to review · مواضع للمراجعة"),
             (f"{s['duration']:.0f}s", "Recording · مدة التسجيل")]
    return '<div class="measurements">' + ''.join(f'<div><strong>{v}</strong><span>{k}</span></div>' for v, k in cards) + '</div>'


def summary_html(s):
    e = html.escape
    banner = "Illustrative animation · synthetic data" if s["synthetic"] else "Your recording · AI-estimated movement"
    ref = s.get("reference_model")
    basis = (f"Compared with a selected reference fitted on {ref['training_cycles']} repetitions." if ref else
             "No reference selected. These are movement measurements; no exercise corrections were inferred.")
    if ref and ref.get("synthetic"):
        basis += " This is an illustrated research guide, not a patient-specific clinical standard."
    basis_ar = (f"تمت المقارنة بمرجع مختار مبني على {ref['training_cycles']} تكرارات." if ref else
                "لم يُختر مرجع للمقارنة. هذه قياسات للحركة، ولم يُستنتج منها تصحيح للتمرين.")
    total = len(s["flags"])
    reviewed = sum(f["status"] != "Pending" for f in s["flags"])
    pain = "Not provided" if s["reported_pain"] is None else f"{s['reported_pain']}/10 (self-reported)"
    feedback = e(s.get("feedback") or "Awaiting physiotherapist feedback. / بانتظار ملاحظات المختص.")
    feature = FEATURES[s.get("primary_feature", "knee_angle")]
    measurement = f"{s.get('measurement_min', s.get('angle_min'))}–{s.get('measurement_max', s.get('angle_max'))} {feature.unit}"
    observations = ''.join(f"<li><b>{e(f['title'])}</b> ({f['start']:.1f}–{f['end']:.1f}s): {e(f['detail'])}<br><span class='cue'>{e(f.get('cue',''))}</span></li>" for f in s["flags"][:8])
    if not observations:
        observations = "<li>No review moments were flagged. This does not establish clinical correctness.</li>"
    return f'''<div class="session-summary"><p class="source-badge">{banner}</p><h3>Session summary · ملخّص الجلسة</h3>
      <p><b>{e(s['exercise'])}</b> · {e(s['plan']['side'])} leg · {e(s['plan'].get('view','Side'))} view</p>
      <p>{e(basis)}</p><p>{s['repetitions']} complete observed movement cycles. {s['coverage']:.0f}% of sampled frames had trackable landmarks. {total} moments available for review; {reviewed} reviewed.</p>
      <p><b>{e(feature.label)}:</b> {measurement}<br><b>Reported pain:</b> {pain}<br><b>Patient notes:</b> {e(s['symptoms'] or 'Not provided.')}</p>
      <h3>Movement observations</h3><ul class="observation-list">{observations}</ul>
      <p class="measurement-note">A difference from a reference requires interpretation against the patient's assigned range, restrictions, and camera view.</p>
      <div dir="rtl" lang="ar"><h3>الملخّص بالعربية</h3><p>{basis_ar}</p><p>رُصدت {s['repetitions']} دورات حركة كاملة، وأمكن تتبّع الحركة في {s['coverage']:.0f}% من العينات. توجد {total} مواضع للمراجعة، تمت مراجعة {reviewed} منها.</p><p>الملاحظات فروق تقديرية قابلة للمراجعة؛ وليست تشخيصًا أو تصريحًا بتغيير البرنامج التأهيلي.</p></div>
      <h3>Physiotherapist feedback · ملاحظات المختص</h3><p class="feedback-copy">{feedback}</p></div>'''


def trace_data(s):
    name = s.get("primary_feature", "knee_angle")
    rows = [{"Seconds": sample["time"], "Measured value": value(sample, name), "Series": "Recorded movement"} for sample in s["samples"]]
    curve = s.get("reference_curve")
    if curve:
        for cycle in s["cycles"]:
            baseline = value(s["samples"][cycle["sample_start"]], name) if name == "hip_height" else 0
            for t, y in zip(np.linspace(cycle["start"], cycle["end"], len(curve)), curve):
                y += baseline
                rows.append({"Seconds": float(t), "Measured value": y, "Series": "Reference shape · phase aligned"})
    return pd.DataFrame(rows)


def cycle_rows(s):
    return [[c["rep"], f"{c['start']:.1f}–{c['end']:.1f}s", c["duration"], c.get("excursion"),
             "; ".join(f["description"] for f in c.get("findings", [])) or "No comparison observation"] for c in s["cycles"]]


def flag_choices(s):
    return [(f"{f['start']:.1f}–{f['end']:.1f}s · {f['title']} [{f['status']}]", f["id"]) for f in s["flags"]]


def flag_description(flag):
    if flag is None:
        return '<div class="review-note">No flagged moments. Review the full recording and assessment basis.</div>'
    e = html.escape
    evidence = ''.join(f"<li>{e(f['feature'])}: {f['observed']} {e(f['unit'])}; reference comparator {f['reference']} {e(f['unit'])}</li>" for f in flag.get("evidence", []))
    return f'''<div class="review-note"><h3>{e(flag['title'])}</h3><p>{e(flag['detail'])}</p><ul>{evidence}</ul>
    <p>Observed at {flag['start']:.2f}–{flag['end']:.2f}s. Clip includes context from {flag['clip_start']:.2f}–{flag['clip_end']:.2f}s.</p>
    <p><b>Feedback:</b> {e(flag.get('cue','Clinician review required.'))}</p><p>{e(flag.get('cue_source','Review the visibility and recording context.'))}</p></div>'''


def reference_description(model):
    e = html.escape
    names = ", ".join(FEATURES[n].label for n in model["templates"])
    approval = "User confirmed review with a physiotherapist" if model["approved_by_user"] else "Reference selected; physiotherapist approval not confirmed"
    origin = "Illustrated research motion; not a patient-specific clinical standard." if model["synthetic"] else "Reference motion estimated from the selected recording."
    return f'''<div class="session-summary"><p class="source-badge">Saved motion model · نموذج الحركة</p>
    <h3>{e(model.get('label',model['exercise']))}</h3><p>{e(model['exercise'])} · {e(model['view'])} view · {model['training_cycles']} reference repetitions.</p>
    <p>{e(origin)}</p><p>Learned reference patterns: {e(names)}. Typical observed cycle: {model['duration_median']:.2f}s.</p><p>{e(approval)}.</p>
    <p class="measurement-note">Method: robust phase-normalised reference fitting and constrained movement alignment. This fits a comparison model; it does not retrain the pose network or establish clinical accuracy.</p></div>'''
