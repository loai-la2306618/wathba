"""Human-readable, printable reports and self-contained review bundles."""

import html
import json
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .analysis import session_analysis


def escape(value):
    return html.escape(str(value))


def render_report(s):
    ref = s.get("reference_model")
    provenance = (f"Reference ID: {ref['reference_session_id']}. {ref['training_cycles']} reference repetitions; {ref['method']}. "
                  f"Source: {'synthetic illustrated research guide' if ref.get('synthetic') else 'selected recorded demonstration'}. "
                  f"Physiotherapist review confirmed by user: {'yes' if ref['approved_by_user'] else 'no'}."
                  if ref else "No comparison reference selected. Measurements only.")
    per_rep = {r['rep']: r['value'] for r in s.get('match_score', {}).get('per_repetition', [])}
    rows = ''.join(f"<tr><td>{c['rep']}</td><td>{c['start']:.2f}–{c['end']:.2f}s</td><td>{c['duration']:.2f}s</td><td>{c.get('excursion', 0):.2f}</td><td>{len(c.get('findings', []))}</td><td>{per_rep.get(c['rep'], '—')}</td></tr>" for c in s["cycles"])
    findings = []
    for f in s["flags"]:
        evidence = ''.join(f"<li>{escape(e['feature'])}: observed {escape(e['observed'])} {escape(e['unit'])}; reference comparator {escape(e['reference'])} {escape(e['unit'])}</li>" for e in f.get("evidence", []))
        clip = Path(f["clip"]).name if f.get("clip") else None
        pictures = ''.join(f'<figure><img src="{escape(Path(f[k]).name)}" alt="{label}"><figcaption>{label}</figcaption></figure>' for k,label in [('picture',f"Patient · {f.get('picture_time',f['start']):.2f}s"),('reference_picture','Therapist comparison')] if f.get(k))
        media = '<div class="pictures">'+pictures+'</div>'+f'<video controls preload="metadata" src="{escape(clip)}"></video>' if clip else ''
        findings.append(f"<article><h3>{escape(f['title'])}</h3><p><b>{'Large reference difference' if f.get('severity')=='red' else 'Reference difference' if f.get('severity')=='yellow' else 'Unable to assess'}</b></p><p>{f['start']:.2f}–{f['end']:.2f}s · {escape(f['status'])}</p><p>{escape(f['detail'])}</p><ul>{evidence}</ul><p><b>Suggested feedback:</b> {escape(f.get('cue', 'Clinician review required.'))}</p>{media}<p><b>Clinician comment:</b> {escape(f.get('comment', '') or 'Not reviewed yet.')}</p></article>")
    limitations = ''.join(f'<li>{escape(v)}</li>' for v in s.get("limitations", []))
    pain = "Not provided" if s.get("reported_pain") is None else f"{s['reported_pain']}/10, self-reported"
    synthetic = '<p class="notice">Illustrative synthetic session. No AI inference on patient footage.</p>' if s["synthetic"] else ''
    match = s.get("match_score", {})
    match_text = (f"{match['value']}/100 reference match. {match['reason']} Method: {match['method']}."
                  if match.get("value") is not None else "Reference match unavailable: " + match.get("reason", "No comparison score was calculated."))
    local_time = datetime.fromisoformat(s["created_at"]).astimezone(ZoneInfo("Asia/Qatar")).strftime("%d %b %Y, %H:%M Doha")
    analysis = session_analysis(s)
    detail_rows = ''.join(f"<tr><td>{r['rep']}</td><td>{r['outward_seconds']:.2f}s</td><td>{r['return_seconds']:.2f}s</td></tr>" for r in analysis['repetitions'])
    feature_rows = ''.join(f"<tr><td>{r['rep']}</td><td>{escape(f['label'])}</td><td>{f['mean_difference']:.3f} {escape(f['unit'])}</td><td>{f['outside_tolerance_pct']:.1f}%</td></tr>" for r in analysis['repetitions'] for f in r['features'] if f['available'])
    def number(v): return 'Not available' if v is None else f'{v:g}'
    analysis_html = f"<h2>Movement evidence</h2><p>{escape(analysis['reason'])}</p><p>Median repetition: {number(analysis['median_duration'])}s. Reference: {number(analysis['reference_duration'])}s. Timing variation: {number(analysis['tempo_variation_pct'])}%. Excursion variation: {number(analysis['excursion_variation_pct'])}%.</p><table><thead><tr><th>Rep</th><th>Movement to peak</th><th>Return from peak</th></tr></thead><tbody>{detail_rows}</tbody></table><table><thead><tr><th>Rep</th><th>Feature</th><th>Mean aligned difference</th><th>Outside comparison tolerance</th></tr></thead><tbody>{feature_rows}</tbody></table><p>{escape(analysis['interpretation'])}</p>"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wathba · {escape(s['label'])}</title><style>
    body{{font:15px/1.65 system-ui,sans-serif;color:#193543;background:#f0f6fa;margin:0;padding:32px}}main{{max-width:950px;margin:auto;background:white;padding:36px;border-radius:14px}}h1{{font-size:32px}}h2{{margin-top:32px}}h3{{margin-bottom:6px}}.meta{{color:#5d7380}}.notice{{padding:14px;background:#e3f1f1}}.metrics{{display:flex;gap:32px;flex-wrap:wrap}}.metrics b{{font-size:28px;display:block}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #dae4eb}}article{{padding:16px 0;border-bottom:1px solid #dae4eb}}video{{width:100%;max-width:560px}}.pictures{{display:flex;gap:12px}}figure{{margin:12px 0;flex:1;min-width:0}}figure img{{width:100%;max-height:300px;object-fit:contain;background:#27323a}}figcaption{{font-size:12px}}p{{white-space:pre-wrap}}@media print{{body{{background:white;padding:0}}main{{padding:0}}video{{display:none}}article{{break-inside:avoid}}}}@media(max-width:600px){{body{{padding:12px}}main{{padding:18px}}}}
    </style></head><body><main><p class="meta">Wathba | وثبة · Exercise review report</p><h1>{escape(s['label'])}</h1>{synthetic}
    <p>{escape(s['exercise'])} · {escape(s['plan']['side'])} side · {escape(s['plan'].get('view','Side'))} camera view</p><p class="meta">Report time: {escape(local_time)}<br>Session: {escape(s['id'])}</p>
    <div class="metrics"><div><b>{s['repetitions']}</b>Observed repetitions</div><div><b>{s['coverage']:.0f}%</b>Trackable samples</div><div><b>{len(s['flags'])}</b>Review moments</div></div>
    <h2>Assessment basis</h2><p>{escape(s.get('assessment_status', 'Demonstration measurements'))}</p><p>{escape(provenance)}</p><p>{escape(s.get('measurement', 'Approximate 2D movement measurements.'))}</p><p>{escape(match_text)}</p>
    <h2>Patient-reported information</h2><p>Pain: {escape(pain)}<br>Notes: {escape(s.get('symptoms') or 'Not provided')}</p>
    <h2>Repetition measurements</h2><p>Movement measure: {escape(s.get('feature_label', '2D knee interior angle'))}; excursion unit: {escape(s.get('feature_unit', 'deg'))}. Reference match is prototype similarity out of 100.</p><table><thead><tr><th>Repetition</th><th>Video interval</th><th>Cycle duration</th><th>Excursion</th><th>Observations</th><th>Reference match</th></tr></thead><tbody>{rows or '<tr><td colspan="6">No complete repetitions were observed.</td></tr>'}</tbody></table>
    {analysis_html}<h2>Evidence and review</h2>{''.join(findings) or '<p>No moments were flagged. This does not establish that the exercise is clinically appropriate.</p>'}
    <h2>Physiotherapist feedback</h2><p>{escape(s.get('feedback') or 'Awaiting review.')}</p>
    <h2>Visibility and interpretation limits</h2><ul>{limitations}</ul><p>Camera footage does not establish ligament healing, muscle strength, or readiness to return to sport.</p>
    <section dir="rtl" lang="ar"><h2>ملخّص للمختص</h2><p>التمرين: {escape(s['exercise'])}. رُصدت {s['repetitions']} تكرارات، وأمكن تتبّع الحركة في {s['coverage']:.0f}% من العينات. توجد {len(s['flags'])} مواضع للمراجعة.</p><p>تمثّل الملاحظات فروقًا قابلة للمراجعة عن المرجع المختار، وليست تشخيصًا أو حكمًا تلقائيًا على سلامة التمرين. يبقى تفسير التسجيل وتعديل الخطة لدى أخصائي العلاج الطبيعي.</p></section>
    <p class="meta">The review bundle includes the playable evidence clips alongside this report. Use your browser's Print command to save a PDF.</p></main></body></html>'''


def write_report(session, directory):
    path = Path(directory) / "physio-report.html"
    path.write_text(render_report(session), encoding="utf-8")
    return str(path)


def bundle(session, directory):
    directory = Path(directory)
    report_path = write_report(session, directory)
    output = directory / "wathba-review.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(report_path, "physio-report.html")
        # Strip server paths from the exported machine-readable report.
        exported = json.loads(json.dumps(session))
        exported["motion_analysis"] = session_analysis(session)
        for key in ("source_video", "annotated_video", "guide_video"):
            if exported.get(key):
                exported[key] = Path(exported[key]).name
        for flag in exported["flags"]:
            for key in ('clip','picture','reference_picture'):
                if flag.get(key):flag[key] = Path(flag[key]).name
        archive.writestr("report.json", json.dumps(exported, ensure_ascii=False, indent=2))
        for flag in session["flags"]:
            for key in ('clip','picture','reference_picture'):
                if flag.get(key) and Path(flag[key]).is_file():
                    archive.write(flag[key], Path(flag[key]).name)
    return str(output)
