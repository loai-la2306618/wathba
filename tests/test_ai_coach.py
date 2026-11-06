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
