from wathba.assessment import assess
from wathba.motion import Plan
from wathba.scoring import reference_match
from test_assessment import recording, reference


def test_same_reference_scores_high_and_pattern_difference_scores_lower():
    samples = recording()
    model = reference(samples)
    normal = assess(samples, Plan(), model)
    score = reference_match(samples, normal['cycles'], model, normal['coverage'])
    changed = recording(amplitudes=[25] * 4, torso_offset=25)
    other = assess(changed, Plan(), model)
    changed_score = reference_match(changed, other['cycles'], model, other['coverage'])
    assert 90 <= score['value'] <= 100
    assert changed_score['value'] < score['value'] - 20
    assert score['clinical_score'] is False
    assert len(score['per_repetition']) == 4


def test_uncertain_or_missing_reference_has_no_score():
    samples = recording()
    model = reference(samples)
    result = assess(samples, Plan(), model)
    assert reference_match(samples, result['cycles'], model, 40)['value'] is None
    assert reference_match(samples, result['cycles'], None, 100)['value'] is None
    assert reference_match(samples, [], model, 100)['value'] is None


def test_front_view_compares_descent_not_body_proportion_offset():
    def front(offset):
        samples = recording(offset=0, amplitudes=[.6]*4, polarity=-1)
        for s in samples:
            s['features'] = {'hip_height': offset + s['angle'], 'torso_lean': 2}
            s['feature_confidence'] = {'hip_height': .95, 'torso_lean': .95}
        return samples
    from wathba.assessment import fit_reference
    p = Plan(view='Front', primary_feature='hip_height')
    model = fit_reference({'id':'a'*32,'plan':p.dict(),'exercise':'Squat','samples':front(2.1),'duration':12,'synthetic':False})
    observed = front(1.3)
    a = assess(observed, p, model)
    score = reference_match(observed, a['cycles'], model, a['coverage'])
    assert a['repetitions'] == 4
    assert not a['flags']
    assert score['value'] >= 90
