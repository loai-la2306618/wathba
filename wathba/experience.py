"""Small patient-facing views; technical evidence lives in the full report."""

import html
from pathlib import Path

from . import storage


def asset_url(path):
    return f"/gradio_api/file={Path(path).resolve()}"


def header():
    logo = asset_url(Path(__file__).resolve().parents[1] / "assets/wathba-logo.png")
    return f'<div class="brand"><img src="{logo}" alt="Wathba logo"><div><strong>Wathba <span lang="ar">وثبة</span></strong><span class="tagline" lang="ar">كل حركة بداية</span></div></div>'


def assigned_exercise(plan, image):
    return f'''<div class="exercise-card"><div class="exercise-art"><img src="{asset_url(image)}" alt="Illustrated squat demonstration"></div>
    <div class="exercise-copy"><span class="plan-tag">Your exercise plan</span><h2>{html.escape(plan.exercise)}</h2><p>A focused set for your {plan.side.lower()}-knee session.</p>
    <div class="exercise-meta"><span>{plan.target_repetitions} repetitions</span><span>{plan.side} leg</span><span>About 1 minute</span></div>
    <p class="quiet">Prototype assignment. Follow the exercise and range agreed with your physiotherapist.</p></div></div>'''


def progress(stage):
    names = ["Watch & record", "Your feedback", "Full report"]
    return '<div class="steps">' + ''.join(f'<span class="{"active" if i == stage else ""}"><b>{i + 1}</b>{name}</span>' for i, name in enumerate(names)) + '</div>'


def stage_heading(plan):
    return f'<div class="intro"><h1>{html.escape(plan.exercise)}</h1><p>{plan.target_repetitions} repetitions · {html.escape(plan.side)} leg · Film from the {plan.view.lower()}.</p><p>Watch the movement, then record your set.</p></div>'


def feedback(s):
    e = html.escape
    score = s.get("match_score", {})
    value = score.get("value")
    target = s["plan"].get("target_repetitions", 5)
    repetitions = s["repetitions"]
    score_text = f'<strong>{value}<small>/100</small></strong><span>Reference match</span>' if value is not None else '<strong>—</strong><span>Reference match unavailable</span>'
    synthetic = '<p class="example-label">Illustrative demo session · no patient AI inference</p>' if s["synthetic"] else ''
    matched = "illustrated guide" if (s.get("reference_model") or {}).get("synthetic") else "selected demonstration"
    note = f"Prototype comparison with the {matched}; not a recovery or medical score." if value is not None else score.get("reason", "No comparison reference selected.")
    items = []
    grouped = {}
    for flag in s["flags"]:
        grouped.setdefault(flag["kind"], []).append(flag)
    for related in list(grouped.values())[:3]:
        flag = related[0]
        if flag["kind"] == "tracking":
            title, detail = "Keep your leg in view", "Part of the recording was unclear. A steady camera helps your physio review the movement."
        elif flag["kind"] == "assessment":
            title, detail = "Try a clearer recording", "Include the whole movement, from the start position through the return."
        else:
            title = {"pace": "A quicker repetition", "range": "A smaller movement", "pattern": "A movement difference"}.get(flag["kind"], "A moment to review")
            detail = flag["detail"].replace("observed movement excursion", "movement range").replace("selected reference", "demonstration")
        if len(related) > 1 and flag["kind"] in ("pace", "range", "pattern"):
            title = {"pace": "A quicker pace", "range": "A smaller movement range", "pattern": "A pattern to review"}[flag["kind"]]
            detail = f"{len(related)} repetitions differed from the demonstration. " + detail
        cue = flag.get("cue", "") if flag.get("cue_source") == "User-confirmed physiotherapist cue" else {
            "pace": "Use the pace assigned by your physiotherapist. The full report has the comparison clips.",
            "range": "Review the highlighted repetition with your physiotherapist before changing your range.",
            "pattern": "Watch the highlighted clip with your physiotherapist.",
            "tracking": "Keep the required joints visible throughout the recording.",
            "assessment": "Include the start and return of each repetition."
        }.get(flag["kind"], "Review the full report with your physiotherapist.")
        items.append(f'<div class="feedback-item"><span class="moment">{flag["start"]:.1f}–{flag["end"]:.1f}s</span><h3>{title}</h3><p>{e(detail)}</p><p class="cue">{e(cue)}</p></div>')
    if not items:
        text = "No differences exceeded the comparison thresholds in the visible repetitions. Your physiotherapist can review the full report." if s.get("reference_model") else "Your visible repetitions and movement measurements are ready for review. A comparison demonstration has not been assigned."
        items.append(f'<div class="feedback-item"><h3>Your recording is ready</h3><p>{text}</p></div>')
    clinician = f'<div class="feedback-item"><h3>From your physiotherapist</h3><p>{e(s["feedback"])}</p></div>' if s.get("feedback") else ""
    return f'''<section class="result-intro">{synthetic}<div class="complete-mark">✓</div><h1>Session complete.</h1><p>You made time for movement. Here’s what we observed.</p></section>
    <div class="result-numbers"><div><strong>{repetitions}<small>/{target}</small></strong><span>Repetitions completed</span></div><div>{score_text}</div></div>
    <p class="score-note">{e(note)}</p><div class="feedback-list">{''.join(items)}{clinician}</div>'''


def recent_sessions():
    items = [s for s in storage.sessions() if s.get("schema_version") == 2 and s.get("kind") != "reference" and not s.get("internal_validation")]
    return [(f"{s['exercise']} · {s['repetitions']} repetitions · {'Illustrative demo' if s['synthetic'] else s['label']}", s["id"]) for s in items[:15]]


def report_heading(s):
    return f'<div class="intro"><h1>Your session report</h1><p>{html.escape(s["exercise"])} · {html.escape(s["plan"]["side"])} leg · {s["repetitions"]} observed repetitions</p></div>'
