import pytest
from wathba.analysis import motion_analysis
from wathba.assessment import assess
from wathba.motion import Plan
from test_assessment import recording, reference


def session(samples, model):
    return {'samples': samples, **assess(samples, Plan(), model)}


def test_distinguishes_timing_variation_and_trunk_deviation():
    model = reference()
    normal = motion_analysis(session(recording(), model), model)
    changed = motion_analysis(session(recording(durations=(3, 1.5, 3, 3), torso_offset=24), model), model)
    assert changed['tempo_variation_pct'] > normal['tempo_variation_pct'] + 10
    for rep in changed['repetitions']:
        assert rep['outward_seconds'] + rep['return_seconds'] == pytest.approx(rep['duration'], abs=.002)
        trunk = next(f for f in rep['features'] if f['name'] == 'torso_lean')
        assert trunk['mean_difference'] == pytest.approx(24)
        assert trunk['outside_tolerance_pct'] == 100


def test_reliable_joint_feature_does_not_imply_other_feature_visible():
    model = reference(); samples = recording()
    for s in samples:
        s['feature_confidence']['torso_lean'] = .1
    a = motion_analysis(session(samples, model), model)
    trunk = next(f for f in a['repetitions'][0]['features'] if f['name'] == 'torso_lean')
    assert trunk['available'] is False
    assert 'mean_difference' not in trunk


def test_no_reference_low_coverage_and_single_rep_do_not_invent_evidence():
    model = reference(); s = session(recording(), model)
    assert not motion_analysis(s)['comparison_available']
    s['coverage'] = 30
    low = motion_analysis(s, model)
    assert not low['comparison_available']
    assert all(not r['features'] for r in low['repetitions'])
    s['cycles'] = s['cycles'][:1]
    assert motion_analysis(s, model)['tempo_variation_pct'] is None
    s['cycles'] = []
    assert not motion_analysis(s, model)['comparison_available']


def test_strict_findings_include_body_part_time_and_tolerance():
    model=reference()
    s=session(recording(torso_offset=30),model)
    findings=[f for c in s['cycles'] for f in c['findings'] if f['feature']=='torso_lean']
    assert findings
    for f in findings:
        assert f['severity']=='red' and f['part']=='Trunk'
        assert f['tolerance']>0 and f['peak_difference']>=30-1e-3
        assert 0<=f['reference_phase']<=1
    s=session(recording(durations=(6,6,6,6)),model)
    assert any('slower' in f['description'] for c in s['cycles'] for f in c['findings'] if f['kind']=='pace')
