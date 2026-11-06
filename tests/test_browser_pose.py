import copy
import pytest
from wathba.browser_pose import browser_samples
from wathba.motion import Plan


def rows():
    points=[{'x':.5,'y':.5,'z':0,'visibility':.95} for _ in range(33)]
    for i,(x,y) in {11:(.4,.2),12:(.6,.2),23:(.45,.5),24:(.55,.5),25:(.4,.7),26:(.6,.7),27:(.4,.9),28:(.6,.9)}.items():
        points[i].update(x=x,y=y)
    return [{'time':i/5,'landmarks':copy.deepcopy(points)} for i in range(6)]


def test_mediapipe_mapping_preserves_left_leg_and_pixel_aspect():
    result=browser_samples(rows(),400,800,1,Plan(view='Front',primary_feature='hip_height'))
    assert result[0]['points'][11]==[180,400]
    assert result[0]['points'][13]==[160,560]
    assert result[0]['features']['hip_height']==pytest.approx(1.3333)
    assert len(result[0]['landmarks33'])==33


def test_missing_person_is_uncertain_not_substituted():
    data=rows();data[2]['landmarks']=[]
    result=browser_samples(data,400,800,1,Plan())
    assert result[2]['points'] is None
    assert result[2]['confidence']==0


@pytest.mark.parametrize('failure',['wrong_count','nan','time_reversal','partial_video'])
def test_invalid_or_partial_browser_tracking_is_rejected(failure):
    data=rows();duration=1
    if failure=='wrong_count':data[0]['landmarks'].pop()
    if failure=='nan':data[0]['landmarks'][23]['x']=float('nan')
    if failure=='time_reversal':data[3]['time']=.1
    if failure=='partial_video':duration=10
    with pytest.raises(ValueError):browser_samples(data,400,800,duration,Plan())


def test_torso_foreshortening_does_not_create_squat_cycles():
    import math
    from wathba.assessment import segment_cycles
    data=[]
    for i in range(73):
        pose=rows()[0]['landmarks']
        # Pelvis and feet stay still while projected torso length changes.
        y=.2+.12*(1-math.cos(2*math.pi*i/18))/2
        pose[11]['y']=pose[12]['y']=y
        data.append({'time':i/6,'landmarks':pose})
    samples=browser_samples(data,400,800,12,Plan(view='Front',primary_feature='hip_height'))
    assert max(s['features']['hip_height'] for s in samples)-min(s['features']['hip_height'] for s in samples)<.001
    assert not segment_cycles(samples,'hip_height')


def test_squat_does_not_count_as_jump_when_feet_stay_on_floor():
    from wathba.assessment import segment_cycles
    import math
    data=[]
    for i in range(145):
        p=rows()[0]['landmarks']
        offset=.12*(1-math.cos(2*math.pi*i/36))/2
        for j in (11,12,23,24):p[j]['y']+=offset
        data.append({'time':i/12,'landmarks':p})
    samples=browser_samples(data,400,800,12,Plan(exercise='Jump',view='Front',primary_feature='foot_lift',sample_fps=12))
    assert max(abs(s['features']['foot_lift']) for s in samples)<.001
    assert not segment_cycles(samples,'foot_lift')


def test_jump_lift_is_distinct_from_squat_and_detects_complete_jumps():
    from wathba.assessment import segment_cycles
    import math
    data=[]
    for i in range(145):
        p=rows()[0]['landmarks']
        phase=(i%48)/48
        lift=.12*max(0,math.sin(2*math.pi*(phase-.2)))
        for v in p:v['y']-=lift
        data.append({'time':i/12,'landmarks':p})
    samples=browser_samples(data,400,800,12,Plan(exercise='Jump',view='Front',primary_feature='foot_lift',sample_fps=12))
    assert len(segment_cycles(samples,'foot_lift'))==3


def test_untrackable_patient_attempt_is_still_saved_for_review(tmp_path,monkeypatch):
    import cv2,numpy as np
    from wathba import storage
    from wathba.browser_pose import process_browser_video
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    source=tmp_path/'attempt.mp4'
    writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),6,(160,160))
    for _ in range(12):writer.write(np.zeros((160,160,3),np.uint8))
    writer.release()
    data=[{'time':i/6,'landmarks':[]} for i in range(12)]
    session=process_browser_video(source,data,exercise='jump')
    saved=storage.load(session['id'])
    assert saved['repetitions']==0 and saved['match_score']['value'] is None
    assert saved['flags'][0]['kind']=='assessment'
    assert saved['source_video'] and saved['flags'][0]['picture']
