"""Browser pose rows (wathba.pose/1) -> validated samples -> motion/report pipeline.

The browser runs YOLOv8n-pose (person selection/reacquisition) and MoveNet
(keypoints on the selected person's crop). One recording uses ONE keypoint model
for every row so 2D measurements are never mixed across models.
"""

import math
import shutil
import time
from collections import Counter

from . import storage
from .assessment import assess, fit_reference, pose_features, normalise_frontal_height, normalise_jump_height, valid
from .motion import Plan
from .pipeline import finish
from .pose_schema import BROWSER_KEYPOINT_MODELS, CAPABILITIES, MODELS, PIPELINE, SCHEMA, to_coco_arrays, unavailable_measurements, validate_keypoints
from .tracking import render_overlay
from .media import open_video

HEIGHT_NORMALISATION = 'static_torso_v1'


def model_label(keypoint_model, detector='yolov8n-pose'):
    parts = [f"{MODELS[keypoint_model]['label']} keypoints"]
    if detector and detector != keypoint_model:
        parts.append(f"{MODELS[detector]['label']} person selection")
    return ' + '.join(parts) + ' · browser ONNX Runtime'


def unassessable_session(source, rows, samples, plan, duration, label, provenance):
    """Retain a recorded attempt even when pose detection cannot assess it."""
    from datetime import datetime, UTC
    from .media import clip_video
    from .pipeline import evidence_picture
    session_id, folder = storage.new_folder()
    target = folder/'source.mp4'
    shutil.copy2(source, target)
    clip, start, end = clip_video(target, folder/'flag-1.mp4', 0, min(duration,5), duration)
    flag = {'id':'flag-1','kind':'assessment','start':0,'end':min(duration,5),
            'title':'Movement could not be assessed','detail':'Required body joints were not reliably detected. No form judgment was made.',
            'cue':'Keep your entire body and feet visible, use a fixed camera, and record again.',
            'evidence':[],'status':'Pending','comment':'','clip':clip,'clip_start':start,'clip_end':end}
    picture = evidence_picture(target, folder/'flag-1.jpg', min(duration/2,2))
    if picture:flag.update(picture=picture,picture_time=min(duration/2,2))
    s={'schema_version':2,'id':session_id,'created_at':datetime.now(UTC).isoformat(),
       'label':label,'exercise':plan.exercise,'plan':plan.dict(),'samples':samples,
       'source_video':str(target),'annotated_video':str(target),'duration':duration,'feedback':'',
       'synthetic':False,'symptoms':'','reported_pain':None,'repetitions':0,'cycles':[],'flags':[flag],
       'primary_feature':plan.primary_feature,'coverage':0,'angle_min':None,'angle_max':None,
       'match_score':{'value':None,'per_repetition':[],'reason':'Insufficient reliable tracking; recording saved for clinician review.'},
       'assessment_status':'Unassessable recording — retained for review','reference_model':None,
       'limitations':['No reliable movement measurements. No corrective form feedback or score was inferred.'],
       'browser_landmarks':rows, **provenance}
    storage.save(s)
    return s


def recording_models(rows):
    """The single keypoint model and detector(s) used by a recording."""
    models = {r.get('model') for r in rows if r.get('keypoints')}
    if len(models) > 1:
        raise ValueError('A recording must use one keypoint model throughout; mixed-model results are not comparable. Retry the analysis.')
    model = next(iter(models), None)
    if model is not None and model not in BROWSER_KEYPOINT_MODELS:
        raise ValueError('Unsupported pose model for browser tracking.')
    detectors = Counter(r.get('detector') for r in rows if r.get('detector'))
    return model, detectors


def browser_samples(rows, width, height, duration, plan):
    if not 5 <= len(rows) <= 2200:
        raise ValueError('Record at least one complete set; up to three minutes is supported.')
    keypoint_model, _ = recording_models(rows)
    result = []
    last = -1
    for row in rows:
        t = float(row['time'])
        if not math.isfinite(t) or t <= last or t < 0 or t > duration + .5:
            raise ValueError('Recording timestamps do not match the video. Please analyse it again.')
        last = t
        if row.get('schema', SCHEMA) != SCHEMA:
            raise ValueError('Unsupported pose schema. Reload the page and analyse again.')
        keypoints = validate_keypoints(row['keypoints']) if row.get('keypoints') else None
        box = row.get('box')
        if box is not None and (len(box) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in box)):
            raise ValueError('Invalid person box.')
        if keypoints:
            points, scores, reliable = to_coco_arrays(keypoints, keypoint_model, width, height)
            features, confidence = pose_features(points, scores, plan.side, reliable=reliable)
        else:
            points, scores, reliable, features, confidence = None, None, None, {}, {}
        result.append({'time': round(t,5), 'angle': features.get('knee_angle'), 'confidence': confidence.get(plan.primary_feature,0),
                       'features': features, 'feature_confidence': confidence,
                       'feature_reliable': {k: v is not None for k, v in features.items()},
                       'points': points, 'scores': scores, 'reliable': reliable, 'box': box,
                       'pose_model': keypoint_model if keypoints else None, 'track_id': row.get('trackId'),
                       'primary_feature': plan.primary_feature,
                       'tracking_reason': '' if keypoints else (row.get('reason') or 'No person detected')})
    # Do not score a fragment as if it represented a whole uploaded recording.
    if result[0]['time'] > 1 or duration - result[-1]['time'] > 1.5:
        raise ValueError('Tracking did not cover the full video. Retry the analysis.')
    tracks = Counter(s['track_id'] for s in result if s['track_id'])
    if len(tracks) > 1:
        # Samples from another track (another person, or an unconfirmed reacquisition) are
        # never stitched into the subject's movement series; the dominant track is kept.
        subject = tracks.most_common(1)[0][0]
        for s in result:
            if s['track_id'] and s['track_id'] != subject:
                s.update(features={}, feature_reliable={}, feature_confidence={}, angle=None, confidence=0, points=None,
                         scores=None, reliable=None, tracking_reason='Different tracked person')
    result = normalise_frontal_height(result)
    if plan.exercise == 'Jump':
        result = normalise_jump_height(result)
        for sample in result:sample['confidence']=sample.get('feature_confidence',{}).get('foot_lift',0)
    return result


def provenance(rows, is_reference):
    keypoint_model, detectors = recording_models(rows)
    detector = 'yolov8n-pose' if detectors.get('yolov8n-pose') else None
    return {'pose_engine': PIPELINE, 'height_normalisation': HEIGHT_NORMALISATION,
            'keypoint_model': keypoint_model, 'detector': detector,
            'model': model_label(keypoint_model, detector) if keypoint_model else 'No pose detected',
            'pose_capabilities': CAPABILITIES, 'unavailable_measurements': unavailable_measurements(),
            'inference_provenance': {
                'runtime': 'browser ONNX Runtime Web (WebAssembly)', 'schema': SCHEMA,
                'keypoint_model': {k: MODELS[keypoint_model][k] for k in ('repository', 'revision', 'license')} if keypoint_model else None,
                'detector': {k: MODELS[detector][k] for k in ('repository', 'revision', 'license')} if detector else None,
                'keypoints': 17, 'depth': None,
                'source_role': 'team-designated therapist reference' if is_reference else 'patient recording'}}


def compatible_reference(reference, keypoint_model):
    """A reference fitted with another model is not comparable (different joint definitions/biases)."""
    if not reference:
        return None, None
    if reference.get('pose_engine') != PIPELINE or reference.get('height_normalisation') != HEIGHT_NORMALISATION:
        return None, 'The therapist reference was prepared with an earlier pose engine. Prepare it again before comparing.'
    if reference.get('keypoint_model') != keypoint_model:
        names = (MODELS.get(reference.get('keypoint_model'), {}).get('label', 'another model'), MODELS.get(keypoint_model, {}).get('label', 'no model'))
        return None, f'Comparison withheld: the reference was tracked with {names[0]} but this recording with {names[1]}; outputs of different models are not compared.'
    return reference, None


def process_browser_video(source, rows, reference_id=None, is_reference=False, label='Squat session', exercise='squat'):
    started = time.monotonic()
    cap, fps, duration = open_video(source)
    width, height = int(cap.get(3)), int(cap.get(4))
    cap.release()
    plan = Plan(exercise='Jump' if exercise=='jump' else 'Squat', side='Left', view='Front', primary_feature='foot_lift' if exercise=='jump' else 'hip_height', reference_id=reference_id, sample_fps=12 if exercise=='jump' else 6, target_repetitions=storage.load_plan().target_repetitions)
    samples = browser_samples(rows, width, height, duration, plan)
    info = provenance(rows, is_reference)
    reference, withheld = compatible_reference(storage.load_reference(reference_id) if reference_id else None, info['keypoint_model'])
    if reference_id and not reference:
        if is_reference:
            raise ValueError(withheld)
        plan = Plan(**{**plan.dict(), 'reference_id': None})
    try:
        assessment = assess(samples, plan, reference)
    except ValueError:
        if is_reference or any(valid(s, plan.primary_feature) for s in samples):
            raise
        return unassessable_session(source, rows, samples, plan, duration, label, info)
    session_id, folder = storage.new_folder()
    target = folder / 'source.mp4'
    shutil.copy2(source, target)
    record = {'width':width,'height':height}
    annotated = render_overlay(target, folder/'annotated.mp4', record, samples, flags=assessment['flags'], reference=reference if assessment['coverage']>=70 else None)
    s = finish(session_id, folder, samples, plan, target, annotated, duration, label, '', None, False, time.monotonic()-started, reference)
    s.update(info)
    s['inference_provenance']['source_role'] = 'team-designated therapist reference' if is_reference else 'patient recording'
    if withheld:
        s['limitations'] = [withheld, *s.get('limitations', [])]
        s['match_score'] = {**s.get('match_score', {}), 'value': None, 'reason': withheld}
    s['analysis_fps'] = round(len(samples)/duration, 2)
    s['browser_landmarks'] = [{k: r.get(k) for k in ('time', 'frameId', 'trackId', 'model', 'detector', 'keypoints', 'box')} for r in rows]
    if is_reference:
        s['kind'] = 'reference'
        model = fit_reference(s, approved=True)
        model.update(label=f'Therapist {exercise} demonstration', pose_engine=PIPELINE, keypoint_model=info['keypoint_model'],
                     source_role='team-designated therapist reference', height_normalisation=HEIGHT_NORMALISATION)
        storage.save_reference(model)
        s['guide_video'] = str(target)
    storage.save(s)
    return s
