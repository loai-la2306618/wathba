"""Wathba AI coach: Qwen3 session summaries and patient Q&A.

Every model answer is checked by wathba/coach.py before it is returned. A failed
answer is regenerated with other seeds, up to ATTEMPTS tries; if it still fails, the summary is
withheld (with the reasons) and a question gets a fixed referral to the
physiotherapist instead of an unchecked answer.
"""

from datetime import UTC, datetime

from . import coach, llm

FALLBACK_ANSWER = {
    'en': "I can't answer that reliably from this session's measurements. Please ask your physiotherapist.",
    'ar': 'لا أستطيع الإجابة عن ذلك بشكل موثوق من قياسات هذه الجلسة. يُرجى سؤال أخصائي العلاج الطبيعي.',
}
ATTEMPTS = 3
# Fixed safety advice: added by the app (not left to the model) when the patient's answers need attention.
SAFETY_NOTE = {
    'en': 'Because you reported pain, instability or swelling, stop if it gets worse and contact your physiotherapist before your next session.',
    'ar': 'بما أنك أبلغت عن ألم أو عدم ثبات أو تورّم، توقّف إذا ازداد الأمر سوءًا وتواصل مع أخصائي العلاج الطبيعي قبل جلستك القادمة.',
}


def _now():
    return datetime.now(UTC).isoformat()


def _checked(messages, facts, lang, task, expect=None, max_new_tokens=320):
    attempts = []
    for seed in range(ATTEMPTS):
        raw, stats = llm.generate_text(messages, seed=seed, max_new_tokens=max_new_tokens)
        text = coach.clean(raw)
        result = coach.check(text, facts, lang, task, expect)
        note = False
        if task == 'feedback' and facts.get('needs_attention') and result['scores'].get('refers_to_physio') is False:
            text, note = f'{text} {SAFETY_NOTE[lang]}', True
            result = coach.check(text, facts, lang, task, expect)
        attempts.append({'text': text, 'issues': result['issues'], 'stats': stats})
        if result['ok']:
            return {'text': text, 'checked': True, 'issues': [], 'stats': stats, 'attempts': len(attempts), 'safety_note_added': note}
    return {'text': None, 'checked': False, 'issues': attempts[-1]['issues'], 'stats': attempts[-1]['stats'], 'attempts': len(attempts)}


def fixed_summary(facts, lang):
    """Plain summary built only from measured facts, for when no model summary passes the checks."""
    ar = lang == 'ar'
    reps, target = facts.get('repetitions_completed'), facts.get('target_repetitions')
    match, coverage = facts.get('reference_match_percent'), facts.get('tracking_coverage_percent')
    answers = facts.get('patient_check_in') or {}
    pain = answers.get('pain_after_exercise_0_to_10')
    lines = []
    if reps:
        lines.append(f'عدد تكراراتك المكتملة: {reps}.' if ar else f"You completed {reps} repetition{'' if reps == 1 else 's'}.")
        if target:
            lines.append(f'وكان هدفك {target}.' if ar else f'Your target was {target}.')
    else:
        lines.append('لم نتمكن من عدّ تكرار مكتمل في هذا التسجيل.' if ar else 'We could not count a complete repetition in this recording.')
    if match is not None:
        lines.append(f'بلغت نسبة تطابق حركتك مع عرض المعالج {match}%.' if ar else f"Your movement matched the therapist's demonstration {match}%.")
    if coverage is not None:
        lines.append(f'تمكّنا من تتبّع حركتك في {coverage}% من التسجيل.' if ar else f'We could follow your movement in {coverage}% of the recording.')
    if facts.get('moments_to_review'):
        lines.append('يعرض تقريرك لحظات للمراجعة.' if ar else 'Your report shows moments to review.')
    if answers.get('pain_during_exercise'):
        lines.append('ذكرت أنك شعرت بألم أثناء التمرين.' if ar else 'You said you felt pain during the exercise.')
    if pain:
        lines.append(f'سجّلت ألمًا بدرجة {pain} من 10 بعد التمرين.' if ar else f'You reported pain of {pain} out of 10 after the exercise.')
    elif pain == 0:
        lines.append('لم تسجّل أي ألم بعد التمرين.' if ar else 'You reported no pain after the exercise.')
    if answers.get('knee_felt_unstable'):
        lines.append('ذكرت أن ركبتك شعرت بعدم ثبات.' if ar else 'You said your knee felt unstable.')
    if answers.get('new_swelling'):
        lines.append('ذكرت أنك لاحظت تورمًا جديدًا.' if ar else 'You said you noticed new swelling.')
    if facts.get('needs_attention'):
        lines.append(SAFETY_NOTE[lang])
    else:
        lines.append('راجع التفاصيل مع أخصائي العلاج الطبيعي في جلستك القادمة.' if ar else 'Go through the details with your physiotherapist at your next session.')
    return ' '.join(lines)


def summary(session, lang):
    facts = coach.session_facts(session)
    out = _checked(coach.feedback_messages(facts, lang), facts, lang, 'feedback')
    if not out['checked']:
        out = {**out, 'text': fixed_summary(facts, lang), 'fixed': True}
    return {**out, 'lang': lang, 'created_at': _now()}


def answer(session, question, lang):
    question = question.strip()[:500]
    if not question:
        raise ValueError('Type a question first.')
    facts = coach.session_facts(session)
    expect = {'defer_to_physio': True} if coach.asks_clinical_decision(question) else None
    out = _checked(coach.answer_messages(facts, question, lang), facts, lang, 'qa', expect, max_new_tokens=160)
    if not out['checked']:
        out['text'] = FALLBACK_ANSWER[lang]
        out['fallback'] = True
    return {**out, 'question': question, 'lang': lang, 'created_at': _now()}


def status():
    text_ok, text_reason = llm.available('text')
    return {'text': {'available': text_ok, 'reason': text_reason, 'model': llm.MODELS[llm.DEFAULT_TEXT]['repo']}}
