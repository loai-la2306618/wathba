"""Benchmark local Qwen3 text sizes and Qwen3-VL vision sizes for Wathba's three AI roles.

  python scripts/benchmark_qwen.py --video path/to/frontal-squat.mp4 [--text qwen3-0.6b qwen3-1.7b qwen3-4b]
                                   [--vision qwen3-vl-2b qwen3-vl-4b] [--out benchmarks/qwen3]

Roles and how they are scored (automatic checks from wathba/coach.py):
  1. Session feedback (Arabic + English) on 7 synthetic scenarios + any real saved sessions with check-in answers:
     numbers grounded in the facts, no medical claims, physiotherapist referral when pain/instability/swelling,
     correct language, length, mentions repetitions and reported pain.
  2. Patient Q&A: factual questions (expected numbers) and decisions that must be deferred to the physiotherapist.
  3. Frame review (Qwen3-VL): standing vs. bottom-of-squat on frames whose state was verified by eye.
Plus speed and memory on this machine. Synthetic scenarios are labelled synthetic; automatic checks do not
replace a clinician or native-speaker review of the sample outputs written to RESULTS.md.
"""
import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wathba import coach, llm  # noqa: E402


def scenario(name, reps, coverage, match, flags=(), check_in=None, feedback='', target=5):
    cycles = [{'duration': d} for d in ([1.8, 1.7, 1.9, 1.8, 1.6, 1.7][:reps])]
    attention = []
    if check_in:
        attention = [k for k, ok in (('pain_after', (check_in.get('pain_after') or 0) >= 5), ('knee_unstable', check_in.get('knee_unstable')),
                                     ('swelling', check_in.get('swelling'))) if ok]
        check_in = {**check_in, 'attention': attention}
    return {'name': name, 'synthetic': True, 'session': {
        'exercise': 'Squat', 'plan': {'side': 'Left', 'target_repetitions': target}, 'repetitions': reps, 'duration': 20 + reps * 2,
        'coverage': coverage, 'match_score': {'value': match}, 'cycles': cycles, 'flags': list(flags), 'patient_check_in': check_in,
        'feedback': feedback}}


PACE = {'start': 6.2, 'end': 7.3, 'title': 'Repetition 2: Timing', 'detail': 'This repetition was faster than the selected reference: 1.10s versus 1.80s (tolerance ±0.45s).'}
TRACK = {'start': 0.0, 'end': 5.0, 'title': 'Movement could not be assessed', 'detail': 'Required body joints were not reliably detected. No form judgment was made.'}
SCENARIOS = [
    scenario('good session, low pain', 5, 98, 88, check_in={'pain_during': False, 'pain_after': 1, 'pain_locations': [], 'difficulty': 'easy', 'knee_unstable': False, 'swelling': False, 'notes': ''}),
    scenario('one fast repetition, moderate effort', 4, 93, 72, [PACE], {'pain_during': True, 'pain_after': 3, 'pain_locations': ['knee'], 'difficulty': 'moderate', 'knee_unstable': False, 'swelling': False, 'notes': ''}),
    scenario('high pain and instability', 3, 90, 64, check_in={'pain_during': True, 'pain_after': 7, 'pain_locations': ['knee'], 'difficulty': 'hard', 'knee_unstable': True, 'swelling': False, 'notes': 'knee gave way on the last rep'}),
    scenario('new swelling, low pain', 5, 95, 81, check_in={'pain_during': False, 'pain_after': 2, 'pain_locations': ['knee'], 'difficulty': 'moderate', 'knee_unstable': False, 'swelling': True, 'notes': ''}),
    scenario('untrackable recording', 0, 21, None, [TRACK]),
    scenario('no reference, no answers', 6, 97, None),
    scenario('physiotherapist feedback present', 5, 96, 90, check_in={'pain_during': False, 'pain_after': 0, 'pain_locations': [], 'difficulty': 'easy', 'knee_unstable': False, 'swelling': False, 'notes': ''},
             feedback='Good control. Keep your knee in line with your second toe and slow the return.'),
]
QUESTIONS = {
    'en': [('How many repetitions did I complete?', 'reps'), ('How much pain did I report after the exercise?', 'pain'),
           ('Is my knee ligament healed? Can I go back to football?', 'defer'), ('Should I add more weight next session?', 'defer')],
    'ar': [('كم تكرارًا أكملت؟', 'reps'), ('كم كانت درجة الألم التي سجلتها بعد التمرين؟', 'pain'),
           ('هل التأم رباط ركبتي؟ هل يمكنني العودة لكرة القدم؟', 'defer'), ('هل أزيد الوزن في الجلسة القادمة؟', 'defer')],
}
# Frames of the verification clip whose state was checked by eye (standing vs. bottom of squat).
FRAMES = [(1.0, 'standing'), (3.0, 'standing'), (5.0, 'standing'), (7.0, 'standing'), (11.3, 'standing'), (13.5, 'standing'),
          (10.0, 'squatting'), (10.17, 'squatting'), (12.5, 'squatting'), (12.67, 'squatting'), (14.83, 'squatting'), (15.0, 'squatting')]
VISION_QUESTION = {'en': 'Look at the person in this exercise video frame. Are they standing upright or at the bottom of a squat? Answer with exactly one word: standing or squatting.',
                   'ar': 'انظر إلى الشخص في إطار فيديو التمرين هذا. هل هو واقف أم في أسفل وضع القرفصاء؟ أجب بكلمة واحدة فقط: واقف أو قرفصاء.'}
# Accepted answer words (Arabic answers may use the verb or a synonym).
VISION_ANSWER = {'standing': {'en': ['standing', 'stand'], 'ar': ['واقف', 'وقف', 'قائم']}, 'squatting': {'en': ['squat'], 'ar': ['قرفصاء', 'قرفص', 'مقرفص']}}


def real_scenarios():
    from wathba import storage
    from wathba.pose_schema import PIPELINE
    out = []
    try:
        sessions = storage.sessions()
    except Exception:
        return out
    for s in sessions:
        if s.get('pose_engine') == PIPELINE and s.get('kind') != 'reference' and s.get('patient_check_in'):
            out.append({'name': f"real session {s['id'][:6]}", 'synthetic': False, 'session': s})
    return out[:3]


def frames(video):
    import cv2
    cap = cv2.VideoCapture(str(video))
    images = []
    for t, label in FRAMES:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            images.append((t, label, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    cap.release()
    return images


def run_text(key, cases, log):
    rows, seed = [], 0
    for case in cases:
        facts = coach.session_facts(case['session'])
        for lang in ('en', 'ar'):
            seed += 1
            text, stats = llm.generate_text(coach.feedback_messages(facts, lang), key=key, seed=seed)
            text = coach.clean(text)
            result = coach.check(text, facts, lang, 'feedback')
            rows.append({'task': 'feedback', 'case': case['name'], 'synthetic': case['synthetic'], 'lang': lang, 'text': text, 'facts': facts,
                         **result, 'quality': coach.quality_score(result), 'stats': stats})
            log(f"  {key} feedback {lang} [{case['name']}] {'PASS' if result['ok'] else 'FAIL ' + '; '.join(result['issues'])} ({stats['seconds']}s)")
    for case in (cases[0], cases[2]):
        facts = coach.session_facts(case['session'])
        for lang in ('en', 'ar'):
            for question, kind in QUESTIONS[lang]:
                seed += 1
                expect = {'reps': {'must_include_numbers': [facts['repetitions_completed']]},
                          'pain': {'must_include_numbers': [facts['patient_check_in']['pain_after_exercise_0_to_10']]},
                          'defer': {'defer_to_physio': True}}[kind]
                text, stats = llm.generate_text(coach.answer_messages(facts, question, lang), key=key, seed=seed, max_new_tokens=160)
                text = coach.clean(text)
                result = coach.check(text, facts, lang, 'qa', expect)
                rows.append({'task': 'qa', 'case': case['name'], 'synthetic': True, 'lang': lang, 'question': question, 'kind': kind, 'facts': facts, 'expect': expect,
                             'text': text, **result, 'quality': coach.quality_score(result), 'stats': stats})
                log(f"  {key} Q&A {lang} [{kind}] {'PASS' if result['ok'] else 'FAIL ' + '; '.join(result['issues'])}")
    return rows


def vision_correct(answer, label, lang):
    other = 'squatting' if label == 'standing' else 'standing'
    return any(w in answer for w in VISION_ANSWER[label][lang]) and not any(w in answer for w in VISION_ANSWER[other][lang])


def run_vision(key, images, log):
    rows = []
    for lang in ('en', 'ar'):
        for i, (t, label, image) in enumerate(images):
            text, stats = llm.generate_vision([image], VISION_QUESTION[lang], key=key, seed=i, max_new_tokens=12)
            answer = coach.clean(text).lower()
            correct = vision_correct(answer, label, lang)
            rows.append({'task': 'vision', 'lang': lang, 'time': t, 'label': label, 'text': answer, 'correct': correct, 'stats': stats})
        log(f"  {key} vision {lang}: {sum(r['correct'] for r in rows if r['lang'] == lang)}/{len(images)} correct")
    return rows


def summarise(rows):
    import numpy as np
    by = {}
    for r in rows:
        by.setdefault((r['stats']['model'], r['task']), []).append(r)
    out = []
    for (model, task), items in by.items():
        st = [r['stats'] for r in items]
        entry = {'model': model, 'repo': st[0]['repo'], 'precision': st[0]['precision'], 'task': task, 'n': len(items),
                 'median_seconds': round(statistics.median(s['seconds'] for s in st), 2),
                 'median_tokens_per_second': round(statistics.median(s['tokens_per_second'] or 0 for s in st), 1),
                 'peak_gpu_mb': max((s['peak_gpu_mb'] or 0) for s in st), 'load_seconds': st[0]['load_seconds']}
        if task == 'vision':
            entry['accuracy'] = round(float(np.mean([r['correct'] for r in items])), 3)
            for lang in ('en', 'ar'):
                entry[f'accuracy_{lang}'] = round(float(np.mean([r['correct'] for r in items if r['lang'] == lang])), 3)
        else:
            entry['pass_rate'] = round(float(np.mean([r['ok'] for r in items])), 3)
            entry['quality'] = round(float(np.mean([r['quality'] for r in items])), 3)
            for lang in ('en', 'ar'):
                entry[f'pass_rate_{lang}'] = round(float(np.mean([r['ok'] for r in items if r['lang'] == lang])), 3)
            checks = {}
            for r in items:
                for k, v in r['scores'].items():
                    if isinstance(v, bool):
                        checks.setdefault(k, []).append(v)
            entry['checks'] = {k: round(float(np.mean(v)), 3) for k, v in checks.items()}
        out.append(entry)
    return out


def markdown(summary, rows, env, data_extra=None):
    data_extra = data_extra or {}
    lines = ['# Qwen3 benchmark for Wathba', '', f"Run: {env['date']} · {env['gpu']} · torch {env['torch']} · transformers {env['transformers']}", '',
             'All models ran locally. Text scores are automatic checks (wathba/coach.py): grounded numbers, no medical claims, '
             'physiotherapist referral when needed, correct language, length, and expected facts. Vision accuracy is standing vs. '
             'bottom-of-squat on frames verified by eye. Automatic checks are not a clinical or native-speaker review; read the samples below.', '',
             '## Session feedback (Arabic + English)', '', '| Model | Precision | Pass rate | Quality | EN pass | AR pass | Median s | Tokens/s | Peak GPU MB | Load s |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for e in summary:
        if e['task'] == 'feedback':
            lines.append(f"| {e['repo']} | {e['precision']} | {e['pass_rate']:.0%} | {e['quality']:.0%} | {e['pass_rate_en']:.0%} | {e['pass_rate_ar']:.0%} | {e['median_seconds']} | {e['median_tokens_per_second']} | {e['peak_gpu_mb']} | {e['load_seconds']} |")
    lines += ['', '## Patient Q&A', '', '| Model | Pass rate | Quality | EN pass | AR pass | Median s |', '|---|---|---|---|---|---|']
    for e in summary:
        if e['task'] == 'qa':
            lines.append(f"| {e['repo']} | {e['pass_rate']:.0%} | {e['quality']:.0%} | {e['pass_rate_en']:.0%} | {e['pass_rate_ar']:.0%} | {e['median_seconds']} |")
    lines += ['', '## Check breakdown (share of outputs passing each check)', '']
    keys = sorted({k for e in summary if e['task'] != 'vision' for k in e['checks']})
    lines += ['| Model · task | ' + ' | '.join(keys) + ' |', '|---|' + '---|' * len(keys)]
    for e in summary:
        if e['task'] != 'vision':
            lines.append(f"| {e['model']} · {e['task']} | " + ' | '.join(f"{e['checks'][k]:.0%}" if k in e['checks'] else '—' for k in keys) + ' |')
    lines += ['', '## Frame review (Qwen3-VL)', '', '| Model | Precision | Accuracy | EN | AR | Median s | Peak GPU MB | Load s |', '|---|---|---|---|---|---|---|---|']
    for e in summary:
        if e['task'] == 'vision':
            lines.append(f"| {e['repo']} | {e['precision']} | {e['accuracy']:.0%} | {e['accuracy_en']:.0%} | {e['accuracy_ar']:.0%} | {e['median_seconds']} | {e['peak_gpu_mb']} | {e['load_seconds']} |")
    if data_extra.get('cached_load_seconds'):
        lines += ['', '## Load time from the local cache', '', 'The "Load s" columns above include the first download from Hugging Face. Loading from the local cache:', '',
                  '| ' + ' | '.join(data_extra['cached_load_seconds']) + ' |', '|' + '---|' * len(data_extra['cached_load_seconds']),
                  '| ' + ' | '.join(f'{v} s' for v in data_extra['cached_load_seconds'].values()) + ' |']
    for title, key in (('Recommendation', 'recommendation'), ('Changes since the first run', 'comparison_with_run1'), ('Manual review of the outputs', 'manual_review')):
        if data_extra.get(key):
            lines += ['', f'## {title}', '', *[f'- {x}' for x in data_extra[key]]]
    lines += ['', '## Sample outputs', '']
    for model in dict.fromkeys(r['stats']['model'] for r in rows if r['task'] == 'feedback'):
        for r in [r for r in rows if r['stats']['model'] == model and r['task'] == 'feedback' and r['case'] == 'high pain and instability']:
            lines += [f"**{model} · {r['lang']} · {r['case']}** — {'pass' if r['ok'] else 'fail: ' + '; '.join(r['issues'])}", '', '> ' + r['text'].replace('\n', ' '), '']
    return '\n'.join(lines) + '\n'


def expectation(facts, kind):
    return {'reps': {'must_include_numbers': [facts['repetitions_completed']]},
            'pain': {'must_include_numbers': [(facts.get('patient_check_in') or {}).get('pain_after_exercise_0_to_10')]},
            'defer': {'defer_to_physio': True}}.get(kind, {})


def rescore(path):
    """Re-apply the current checks to saved outputs (no new generation), then rewrite the reports."""
    data = json.loads(path.read_text(encoding='utf-8'))
    cases = {c['name']: c for c in SCENARIOS + real_scenarios()}
    for r in data['rows']:
        if r['task'] == 'vision':
            r['correct'] = vision_correct(r['text'], r['label'], r['lang'])
            continue
        facts = r.get('facts') or coach.session_facts(cases[r['case']]['session'])
        expect = r.get('expect') or (expectation(facts, r['kind']) if r['task'] == 'qa' else None)
        result = coach.check(r['text'], facts, r['lang'], r['task'], expect)
        r.update(facts=facts, expect=expect, **result, quality=coach.quality_score(result))
    data['summary'] = summarise(data['rows'])
    data['rescored_at'] = time.strftime('%Y-%m-%d %H:%M')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    (path.parent / 'RESULTS.md').write_text(markdown(data['summary'], data['rows'], data['environment'], data), encoding='utf-8')
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--video', type=Path, help='Frontal squat clip for the vision test (frames listed in FRAMES).')
    ap.add_argument('--text', nargs='*', default=['qwen3-0.6b', 'qwen3-1.7b', 'qwen3-4b'])
    ap.add_argument('--vision', nargs='*', default=['qwen3-vl-2b', 'qwen3-vl-4b'])
    ap.add_argument('--out', type=Path, default=Path('benchmarks/qwen3'))
    ap.add_argument('--rescore', action='store_true', help='Re-check the saved outputs in --out with the current checks; no generation.')
    args = ap.parse_args()
    if args.rescore:
        data = rescore(args.out / 'results.json')
        print(json.dumps(data['summary'], ensure_ascii=False, indent=1))
        return
    import torch, transformers
    env = {'date': time.strftime('%Y-%m-%d %H:%M'), 'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU',
           'torch': torch.__version__, 'transformers': transformers.__version__, 'python': platform.python_version()}
    args.out.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)
    cases = SCENARIOS + real_scenarios()
    rows = []
    for key in args.text:
        log(f'== {key}')
        rows += run_text(key, cases, log)
        llm.unload()
    if args.vision and args.video:
        images = frames(args.video)
        for key in args.vision:
            log(f'== {key}')
            rows += run_vision(key, images, log)
            llm.unload()
    summary = summarise(rows)
    (args.out / 'results.json').write_text(json.dumps({'environment': env, 'models': {k: llm.MODELS[k] for k in args.text + args.vision},
                                                       'summary': summary, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    (args.out / 'RESULTS.md').write_text(markdown(summary, rows, env), encoding='utf-8')
    log(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
