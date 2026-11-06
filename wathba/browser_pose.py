"""MediaPipe browser landmark validation and shared motion/report pipeline."""

import math
import shutil
import time
from pathlib import Path

import numpy as np

from . import storage
from .assessment import assess, fit_reference, pose_features, normalise_frontal_height, normalise_jump_height
from .motion import Plan
from .pipeline import finish
from .tracking import render_overlay
from .media import open_video


def unassessable_session(source, rows, samples, plan, duration, label):
    """Retain a recorded attempt even when pose detection cannot assess it."""
    from datetime import datetime, UTC
    from .media import clip_video
    from .pipeline import evidence_picture
    session_id, folder = storage.new_folder()
    target = folder/'source.mp4'
    shutil.copy2(source, target)
    clip, start, end = clip_video(target, folder/'flag-1.mp4', 0, min(duration,5), duration)
    flag = {'id':'flag-1','kind':'assessment','start':0,'end':min(duration,5),
            'title':'Movement could not be assessed','detail':'Required body landmarks were not reliably visible. No form judgment was made.',
            'cue':'Keep your entire body and feet visible, use a fixed camera, and record again.',
            'evidence':[],'status':'Pending','comment':'','clip':clip,'clip_start':start,'clip_end':end}
    picture = evidence_picture(target, folder/'flag-1.jpg', min(duration/2,2))
    if picture:flag.update(picture=picture,picture_time=min(duration/2,2))
    s={'schema_version':2,'id':session_id,'created_at':datetime.now(UTC).isoformat(),
       'label':label,'exercise':plan.exercise,'plan':plan.dict(),'samples':samples,
       'source_video':str(target),'annotated_video':str(target),'duration':duration,'feedback':'',
       'model':ENGINE,'pose_engine':'mediapipe-pose-landmarker-full','height_normalisation':'static_torso_v1',
       'synthetic':False,'symptoms':'','reported_pain':None,'repetitions':0,'cycles':[],'flags':[flag],
       'primary_feature':plan.primary_feature,'coverage':0,'angle_min':None,'angle_max':None,
       'match_score':{'value':None,'per_repetition':[],'reason':'Insufficient reliable tracking; recording saved for clinician review.'},
       'assessment_status':'Unassessable recording — retained for review','reference_model':None,
       'limitations':['No reliable movement measurements. No corrective form feedback or score was inferred.'],
       'browser_landmarks':rows}
    storage.save(s)
    return s

ENGINE = 'Google MediaPipe Pose Landmarker Full · browser · 0.10.32'
# MediaPipe's 33-landmark order to the COCO-17 order used by our feature code.
COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]


def browser_samples(rows, width, height, duration, plan):
    if not 5 <= len(rows) <= 2200:
        raise ValueError('Record at least one complete set; up to three minutes is supported.')
    result = []
    last = -1
    for row in rows:
        t = float(row['time'])
        if not math.isfinite(t) or t <= last or t < 0 or t > duration + .5:
            raise ValueError('Recording timestamps do not match the video. Please analyse it again.')
        last = t
        landmarks = row.get('landmarks', [])
        if landmarks and len(landmarks) != 33:
            raise ValueError('Expected 33 MediaPipe landmarks per detected person.')
        for p in landmarks:
            for key in ('x','y','z','visibility'):
                v = float(p.get(key, 0))
                if not math.isfinite(v) or abs(v) > 100:
                    raise ValueError('Invalid body-tracking coordinates.')
        if landmarks:
            points = [[float(landmarks[i]['x']) * width, float(landmarks[i]['y']) * height] for i in COCO]
            scores = [max(0, min(1, float(landmarks[i].get('visibility', 0)))) for i in COCO]
            features, confidence = pose_features(points, scores, plan.side)
        else:
            points, scores, features, confidence = None, None, {}, {}
        result.append({'time': round(t,5), 'angle': features.get('knee_angle'), 'confidence': confidence.get(plan.primary_feature,0),
                       'features': features, 'feature_confidence': confidence, 'points': points, 'scores': scores,
                       'primary_feature': plan.primary_feature, 'landmarks33': landmarks,
                       'tracking_reason': '' if landmarks else 'No person detected'})
    # Do not score a fragment as if it represented a whole uploaded recording.
    if result[0]['time'] > 1 or duration - result[-1]['time'] > 1.5:
        raise ValueError('Tracking did not cover the full video. Retry the analysis.')
    result = normalise_frontal_height(result)
    if plan.exercise == 'Jump':
        result = normalise_jump_height(result)
        for sample in result:sample['confidence']=sample.get('feature_confidence',{}).get('foot_lift',0)
    return result


def process_browser_video(source, rows, reference_id=None, is_reference=False, label='Squat session', exercise='squat'):
    started = time.monotonic()
    cap, fps, duration = open_video(source)
    width, height = int(cap.get(3)), int(cap.get(4))
    cap.release()
    plan = Plan(exercise='Jump' if exercise=='jump' else 'Squat', side='Left', view='Front', primary_feature='foot_lift' if exercise=='jump' else 'hip_height', reference_id=reference_id, sample_fps=12 if exercise=='jump' else 6, target_repetitions=storage.load_plan().target_repetitions)
    samples = browser_samples(rows, width, height, duration, plan)
    reference = storage.load_reference(reference_id) if reference_id else None
    if reference and (reference.get('pose_engine')!='mediapipe-pose-landmarker-full' or reference.get('height_normalisation')!='static_torso_v1'):
        raise ValueError('Prepare a compatible MediaPipe therapist reference before comparing this recording.')
    try:
        assessment = assess(samples, plan, reference)
    except ValueError:
        if is_reference or any(s.get('feature_confidence',{}).get(plan.primary_feature,0)>=.45 and s.get('features',{}).get(plan.primary_feature) is not None for s in samples):
            raise
        return unassessable_session(source, rows, samples, plan, duration, label)
    session_id, folder = storage.new_folder()
    target = folder / 'source.mp4'
    shutil.copy2(source, target)
    record = {'width':width,'height':height}
    annotated = render_overlay(target, folder/'annotated.mp4', record, samples, flags=assessment['flags'], reference=reference if assessment['coverage']>=70 else None)
    s = finish(session_id, folder, samples, plan, target, annotated, duration, label, '', None, False, time.monotonic()-started, reference)
    s['model'] = ENGINE
    s['pose_engine'] = 'mediapipe-pose-landmarker-full'
    s['height_normalisation'] = 'static_torso_v1'
    s['inference_provenance'] = {'runtime':'browser WebAssembly/WebGL', 'package':'@mediapipe/tasks-vision@0.10.32',
                               'model':'pose_landmarker_full/float16/1', 'landmarks':33,
                               'source_role':'team-designated therapist reference' if is_reference else 'patient recording'}
    s['analysis_fps'] = round(len(samples)/duration, 2)
    s['browser_landmarks'] = [{'time':r['time'],'landmarks':r.get('landmarks',[])} for r in rows]
    if is_reference:
        s['kind'] = 'reference'
        model = fit_reference(s, approved=True)
        model.update(label=f'Therapist {exercise} demonstration', pose_engine=s['pose_engine'], source_role='team-designated therapist reference',
                     height_normalisation='static_torso_v1')
        storage.save_reference(model)
        s['guide_video'] = str(target)
    storage.save(s)
    return s
