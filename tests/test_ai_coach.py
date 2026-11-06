import pytest
from fastapi.testclient import TestClient

from wathba import ai, coach, llm, storage, webapp

FACTS = {'repetitions_completed': 3, 'target_repetitions': 5, 'tracking_coverage_percent': 90, 'reference_match_percent': 64,
         'needs_attention': True, 'patient_check_in': {'pain_after_exercise_0_to_10': 7, 'new_swelling': False, 'knee_felt_unstable': True}}
GOOD_EN = 'You completed 3 repetitions with 90% tracking. You reported pain of 7 out of 10 and your knee felt unstable, so stop if it gets worse and contact your physiotherapist before your next session.'
GOOD_AR = 'أكملت 3 تكرارات، وسجّلت ألمًا بدرجة 7 من 10 وشعرت بعدم ثبات في الركبة. توقّف إذا ازداد الأمر سوءًا وتواصل مع أخصائي العلاج الطبيعي قبل جلستك القادمة.'


@pytest.mark.parametrize('text,lang', [(GOOD_EN, 'en'), (GOOD_AR, 'ar')])
def test_grounded_safe_answers_pass(text, lang):
    result = coach.check(text, FACTS, lang, 'feedback')
    assert result['ok'], result['issues']


@pytest.mark.parametrize('text,lang,issue', [
    ('You completed 3 repetitions in 42 seconds. Pain was 7. Contact your physiotherapist.', 'en', 'ungrounded numbers'),
    ('You completed 3 repetitions. Your ligament is healed. Pain 7. Contact your physiotherapist.', 'en', 'medical claim'),
    ('You completed 3 repetitions with pain 7 out of 10. Keep going!', 'en', 'does not refer to the physiotherapist'),
    ('You completed 5 repetitions with pain 7. Contact your physiotherapist.', 'en', 'wrong repetition count'),
    ('You completed 3 repetitions with pain 7 and new swelling. Contact your physiotherapist.', 'en', 'contradicts patient answer'),
    ('You completed 3 repetitions with pain 7. Contact your physiotherapist.', 'ar', 'wrong language'),
    ('أكملت 3 تكرارات بنسبة 百分比. الألم 7. تواصل مع أخصائي العلاج الطبيعي.', 'ar', 'foreign script'),
    ('أكملت 3 تكرارات والألم 7، وهذا تشخيص لتمزق. تواصل مع أخصائي العلاج الطبيعي.', 'ar', 'medical claim'),
])
def test_unsafe_or_invented_answers_fail(text, lang, issue):
    result = coach.check(text, FACTS, lang, 'feedback')
    assert not result['ok'] and any(i.startswith(issue) for i in result['issues']), result['issues']


def test_target_mention_is_not_a_wrong_count_and_number_words_count():
    ok = coach.check('You did three repetitions out of a target of 5 repetitions. Pain 7/10; please contact your physiotherapist.', FACTS, 'en', 'feedback')
    assert ok['scores']['correct_repetitions'] and ok['scores']['mentions_repetitions'], ok['issues']


@pytest.mark.parametrize('sentence', ['كانت حركتك مختلفة قليلًا عن عرض المعالج.', 'تختلف سرعتك بين التكرارات.', 'شاهد التلفاز بعد التمرين.'])
def test_ordinary_arabic_words_are_not_damage_claims(sentence):
    assert coach.check(f'أكملت 3 تكرارات. {sentence}', {'repetitions_completed': 3}, 'ar', 'feedback')['scores']['no_medical_claims']


@pytest.mark.parametrize('claim', ['يوجد تلف في الركبة.', 'أرى التلف في الرباط.', 'هذا دليل على وجود تلف.', 'حدث تلفا واضحا.', 'أصيب بالتلف.', 'قد يتلف الرباط.', 'هناك علامات للتلف.'])
def test_arabic_damage_claims_are_still_caught(claim):
    assert not coach.check(f'أكملت 3 تكرارات. {claim}', {'repetitions_completed': 3}, 'ar', 'feedback')['scores']['no_medical_claims']


@pytest.mark.parametrize('text,lang', [
    ('Please discuss this with your physiotherapist before you change anything.', 'en'),
    ('ناقش هذا الأمر مع أخصائي العلاج الطبيعي قبل أي تغيير.', 'ar'),
])
def test_discussing_with_the_physiotherapist_counts_as_a_referral(text, lang):
    assert coach.check(text, {}, lang, 'qa', {'defer_to_physio': True})['scores']['refers_to_physio']


@pytest.mark.parametrize('text,value,expected', [
    ('أكملت أربعة تكرارات.', 4, True), ('أكملت خمسة تكرارات.', 5, True), ('أكملت ستة تكرارات.', 6, True), ('أكملت عشرة تكرارات.', 10, True),
    ('أكملت ستة تكرارات.', 5, False), ('أكملت خمسة تكرارات.', 4, False),
])
def test_arabic_number_words_match_their_values(text, value, expected):
    assert coach.mentions_number(text, value, 'ar') is expected


LOW_PAIN = {'repetitions_completed': 3, 'tracking_coverage_percent': 90, 'needs_attention': False,
            'patient_check_in': {'pain_during_exercise': False, 'pain_after_exercise_0_to_10': 2}}


@pytest.mark.parametrize('text,lang', [
    ('You completed 3 repetitions. No pain reported, keep up the good work.', 'en'),
    ('You finished 3 repetitions without any pain.', 'en'),
    ('You did not report any pain and completed 3 repetitions.', 'en'),
    ('أتممت 3 تكرارات بسلاسة وبدون ألم.', 'ar'),
    ('أكملت 3 تكرارات ولم تشعر بأي ألم.', 'ar'),
])
def test_summary_cannot_deny_reported_pain(text, lang):
    result = coach.check(text, LOW_PAIN, lang, 'feedback')
    assert 'contradicts patient answer (pain reported)' in result['issues'], result['issues']
    assert result['scores']['consistent_with_answers'] is False


@pytest.mark.parametrize('text,lang', [
    ('You completed 3 repetitions with no pain during the exercise, and pain of 2 out of 10 afterwards.', 'en'),
    ('أكملت 3 تكرارات دون ألم أثناء التمرين، وسجّلت ألمًا بدرجة 2 من 10 بعده.', 'ar'),
    ('You completed 3 repetitions and reported pain of 2 out of 10.', 'en'),
])
def test_accurate_pain_statements_are_allowed(text, lang):
    result = coach.check(text, LOW_PAIN, lang, 'feedback')
    assert result['scores']['consistent_with_answers'], result['issues']


@pytest.mark.parametrize('text,lang', [
    ('لم يلاحظ ألم أثناء أو بعد التمرين، حيث بلغ مستوى الألم 2 من 10.', 'ar'),
    ('أكملت 3 تكرارات دون ألم بعد التمرين وأثناءه.', 'ar'),
    ('You had no pain during or after the exercise, with a score of 2 out of 10.', 'en'),
])
def test_denying_pain_after_the_exercise_is_caught_even_when_during_is_mentioned(text, lang):
    assert 'contradicts patient answer (pain reported)' in coach.check(text, LOW_PAIN, lang, 'feedback')['issues']


@pytest.mark.parametrize('text,lang', [
    ('You completed 3 repetitions and reported mild pain in the knee after the exercise.', 'en'),
    ('أكملت 3 تكرارات وسجّلت ألمًا خفيفًا في الركبة.', 'ar'),
])
def test_summary_must_give_the_pain_score(text, lang):
    assert 'reported pain score missing' in coach.check(text, LOW_PAIN, lang, 'feedback')['issues']


def test_no_pain_is_fine_when_the_patient_reported_none():
    facts = {**LOW_PAIN, 'patient_check_in': {'pain_during_exercise': False, 'pain_after_exercise_0_to_10': 0}}
    assert coach.check('You completed 3 repetitions with no pain.', facts, 'en', 'feedback')['scores']['consistent_with_answers']


@pytest.mark.parametrize('question,expected', [
    ('Can I go back to football?', True), ('Should I add more weight next session?', True), ('Is my knee healed?', True),
    ('هل يمكنني العودة لكرة القدم؟', True), ('هل أزيد الوزن في الجلسة القادمة؟', True), ('هل التأم رباط ركبتي؟', True),
    ('How many repetitions did I complete?', False), ('How much pain did I report?', False),
    ('كم تكرارًا أكملت؟', False), ('كم كانت درجة الألم التي سجلتها؟', False),
])
def test_clinical_questions_are_recognised(question, expected):
    assert coach.asks_clinical_decision(question) is expected


def test_session_facts_use_only_measured_values():
    s = {'exercise': 'Squat', 'plan': {'side': 'Left', 'target_repetitions': 5}, 'repetitions': 3, 'duration': 25.4, 'coverage': 90.2,
         'match_score': {'value': 64}, 'cycles': [{'duration': 1.6}, {'duration': 1.8}, {'duration': 2.0}],
         'flags': [{'start': 6.21, 'end': 7.3, 'title': 'Repetition 2: Timing', 'detail': 'faster'}],
         'patient_check_in': {'pain_after': 7, 'knee_unstable': True, 'attention': ['pain_after', 'knee_unstable']}, 'feedback': ''}
    f = coach.session_facts(s)
    assert f['repetitions_completed'] == 3 and f['median_repetition_seconds'] == 1.8 and f['needs_attention']
    assert f['moments_to_review'][0]['from_second'] == 6.2 and f['physiotherapist_feedback'] is None


def fake_llm(monkeypatch, replies):
    calls = []

    def generate(messages, key=None, max_new_tokens=320, seed=0):
        calls.append({'messages': messages, 'seed': seed})
        return replies[min(len(calls) - 1, len(replies) - 1)], {'model': 'fake', 'repo': 'Qwen/fake', 'seconds': .1}
    monkeypatch.setattr(llm, 'generate_text', generate)
    return calls


def session_with(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(webapp, 'prepare_library', lambda: tmp_path)
    s = {'schema_version': 2, 'id': 'a'*32, 'created_at': '2026-11-06T16:00:00+00:00', 'label': 'Patient squat session', 'exercise': 'Squat',
         'plan': {'side': 'Left', 'view': 'Front', 'target_repetitions': 5, 'reference_id': None}, 'samples': [], 'source_video': str(tmp_path/'x.mp4'),
         'annotated_video': str(tmp_path/'x.mp4'), 'duration': 25, 'feedback': '', 'model': 'test', 'pose_engine': 'wathba-pose-coco17-v1',
         'height_normalisation': 'static_torso_v1', 'synthetic': False, 'symptoms': '', 'reported_pain': 7, 'repetitions': 3, 'cycles': [],
         'flags': [], 'coverage': 90, 'match_score': {'value': 64, 'reason': ''}, 'limitations': [],
         'patient_check_in': {'pain_after': 7, 'knee_unstable': True, 'swelling': False, 'attention': ['pain_after', 'knee_unstable']}}
    monkeypatch.setattr('wathba.reporting.write_report', lambda *_: None)
    (tmp_path/s['id']).mkdir()
    storage.save(s)
    return TestClient(webapp.create_app()), s['id']


def test_summary_is_checked_retried_and_stored(tmp_path, monkeypatch):
    client, sid = session_with(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, 'available', lambda kind='text': (True, ''))
    calls = fake_llm(monkeypatch, ['You did 9 reps. Your knee is healed.', GOOD_EN])
    r = client.post(f'/api/session/{sid}/ai/summary', json={'consent': True, 'lang': 'en'})
    assert r.status_code == 200 and r.json()['checked'] and r.json()['attempts'] == 2
    assert [c['seed'] for c in calls] == [0, 1]
    assert '"repetitions_completed": 3' in calls[0]['messages'][1]['content']
    assert storage.load(sid)['ai']['summary']['en']['text'] == GOOD_EN


def test_unchecked_summary_is_withheld_and_question_falls_back(tmp_path, monkeypatch):
    client, sid = session_with(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, 'available', lambda kind='text': (True, ''))
    fake_llm(monkeypatch, ['You did 9 reps and your ACL is healed.'])
    r = client.post(f'/api/session/{sid}/ai/summary', json={'consent': True, 'lang': 'en'}).json()
    assert r['checked'] is False and r['text'] is None and r['issues']
    q = client.post(f'/api/session/{sid}/ai/ask', json={'consent': True, 'lang': 'ar', 'question': 'هل التأم الرباط؟'}).json()
    assert q['fallback'] and q['text'] == ai.FALLBACK_ANSWER['ar']
    assert storage.load(sid)['ai']['questions'][0]['question'] == 'هل التأم الرباط؟'


@pytest.mark.parametrize('lang,reply', [
    ('en', 'You completed 3 repetitions with no pain. Contact your physiotherapist before your next session.'),
    ('ar', 'أكملت 3 تكرارات بدون ألم. تواصل مع أخصائي العلاج الطبيعي قبل جلستك القادمة.'),
])
def test_summary_denying_reported_pain_is_withheld(tmp_path, monkeypatch, lang, reply):
    client, sid = session_with(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, 'available', lambda kind='text': (True, ''))
    calls = fake_llm(monkeypatch, [reply])
    r = client.post(f'/api/session/{sid}/ai/summary', json={'consent': True, 'lang': lang}).json()
    assert r['checked'] is False and r['text'] is None and len(calls) == 2
    assert 'contradicts patient answer (pain reported)' in r['issues']


@pytest.mark.parametrize('lang,question,reply', [
    ('en', 'Can I go back to football?', 'I do not have that information.'),
    ('ar', 'هل يمكنني العودة لكرة القدم؟', 'لا تملك هذه المعلومة.'),
])
def test_clinical_question_without_referral_gets_the_fixed_referral(tmp_path, monkeypatch, lang, question, reply):
    client, sid = session_with(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, 'available', lambda kind='text': (True, ''))
    fake_llm(monkeypatch, [reply])
    r = client.post(f'/api/session/{sid}/ai/ask', json={'consent': True, 'lang': lang, 'question': question}).json()
    assert r['fallback'] and r['text'] == ai.FALLBACK_ANSWER[lang]


def test_clinical_question_with_a_referral_keeps_the_model_answer(tmp_path, monkeypatch):
    client, sid = session_with(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, 'available', lambda kind='text': (True, ''))
    answer = 'Please ask your physiotherapist before you go back to football.'
    fake_llm(monkeypatch, [answer])
    r = client.post(f'/api/session/{sid}/ai/ask', json={'consent': True, 'lang': 'en', 'question': 'Can I go back to football?'}).json()
    assert r['checked'] and r['text'] == answer and not r.get('fallback')


def test_ordinary_question_does_not_need_a_referral(tmp_path, monkeypatch):
    client, sid = session_with(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, 'available', lambda kind='text': (True, ''))
    fake_llm(monkeypatch, ['أكملت 3 تكرارات.'])
    r = client.post(f'/api/session/{sid}/ai/ask', json={'consent': True, 'lang': 'ar', 'question': 'كم تكرارًا أكملت؟'}).json()
    assert r['checked'] and r['text'] == 'أكملت 3 تكرارات.' and not r.get('fallback')


def test_consent_and_availability_are_enforced(tmp_path, monkeypatch):
    client, sid = session_with(tmp_path, monkeypatch)
    assert client.post(f'/api/session/{sid}/ai/summary', json={'lang': 'en'}).status_code == 400
    monkeypatch.setattr(llm, 'available', lambda kind='text': (False, 'Qwen3 needs optional packages'))
    r = client.post(f'/api/session/{sid}/ai/summary', json={'consent': True, 'lang': 'en'})
    assert r.status_code == 503 and 'optional packages' in r.json()['detail']
    assert client.post(f'/api/session/{sid}/ai/summary', json={'consent': True, 'lang': 'fr'}).status_code == 422
    assert client.get('/api/config').json()['ai']['text']['model'].startswith('Qwen/')


@pytest.mark.parametrize('text,lang', [
    ('I do not have information about whether your knee ligament is healed. Please ask your physiotherapist.', 'en'),
    ('لا أعرف إن كان الرباط قد التأم. يُرجى استشارة مُعالجك أو مُختص العلاج الطبيعي.', 'ar'),
])
def test_refusals_with_negated_claims_and_diacritics_pass(text, lang):
    result = coach.check(text, {'repetitions_completed': 3, 'needs_attention': False}, lang, 'qa', {'defer_to_physio': True})
    assert result['ok'], result['issues']


def test_affirmative_claim_inside_words_like_know_is_still_caught():
    result = coach.check('You know your ligament is healed.', {'repetitions_completed': 3}, 'en', 'qa')
    assert not result['scores']['no_medical_claims']


def test_derived_difference_is_grounded_but_invented_number_is_not():
    facts = {'moments_to_review': [{'detail': '1.10s versus 1.80s'}], 'repetitions_completed': 4}
    assert coach.ungrounded_numbers('It was 0.70 seconds faster', facts) == []
    assert coach.ungrounded_numbers('It was 2.5 seconds faster', facts) == ['2.5']


def test_missing_referral_gets_the_fixed_safety_note(tmp_path, monkeypatch):
    client, sid = session_with(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, 'available', lambda kind='text': (True, ''))
    fake_llm(monkeypatch, ['أكملت 3 تكرارات وسجّلت ألمًا بدرجة 7 من 10.'])
    r = client.post(f'/api/session/{sid}/ai/summary', json={'consent': True, 'lang': 'ar'}).json()
    assert r['checked'] and r['safety_note_added'] and r['text'].endswith(ai.SAFETY_NOTE['ar'])
