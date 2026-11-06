"""Wathba AI coach: Qwen3 session summaries, patient Q&A and Qwen3-VL frame review.

Every model answer is checked by wathba/coach.py before it is returned. A failed
answer is regenerated once with another seed; if it still fails, the summary is
withheld (with the reasons) and a question gets a fixed referral to the
physiotherapist instead of an unchecked answer.
"""

from datetime import UTC, datetime

from . import coach, llm

FALLBACK_ANSWER = {
    'en': "I can't answer that reliably from this session's measurements. Please ask your physiotherapist.",
    'ar': 'لا أستطيع الإجابة عن ذلك بشكل موثوق من قياسات هذه الجلسة. يُرجى سؤال أخصائي العلاج الطبيعي.',
}
ATTEMPTS = 2
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


def summary(session, lang):
    facts = coach.session_facts(session)
    out = _checked(coach.feedback_messages(facts, lang), facts, lang, 'feedback')
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


def review_frames(session, lang, limit=4):
    """Qwen3-VL description of repetition start/bottom frames. Experimental; never changes the score."""
    from .vitpose_service import read_frames
    times = []
    for c in session.get('cycles', [])[:2]:
        times += [c['start'], c['peak_time']]
    if not times:
        raise ValueError('No complete repetitions to review.')
    frames = [f for f in read_frames(session['source_video'], times[:limit]) if f is not None]
    if not frames:
        raise ValueError('Could not read frames from this recording.')
    raw, stats = llm.generate_vision(frames, coach.VISION_PROMPT[lang])
    text = coach.clean(raw)
    facts = {'frames': len(frames), 'times': [round(t, 1) for t in times[:limit]], 'needs_attention': False}
    result = coach.check(text, facts, lang, 'vision')
    claims = not result['scores'].get('no_medical_claims', True)
    return {'text': None if claims else text, 'checked': not claims, 'issues': result['issues'] if claims else [],
            'frame_times': facts['times'], 'stats': stats, 'lang': lang, 'created_at': _now()}


def status():
    text_ok, text_reason = llm.available('text')
    vision_ok, vision_reason = llm.available('vision')
    return {'text': {'available': text_ok, 'reason': text_reason, 'model': llm.MODELS[llm.DEFAULT_TEXT]['repo']},
            'vision': {'available': vision_ok, 'reason': vision_reason, 'model': llm.MODELS[llm.DEFAULT_VISION]['repo']}}
