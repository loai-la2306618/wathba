"""Server-side ViTPose-B check on selected frames of a saved recording.

usyd-community/vitpose-base-simple ships PyTorch safetensors only (~344 MB,
86M parameters) and is a top-down model: it needs a person box per frame. It is
therefore run on the Wathba backend, on demand, using the person boxes chosen by
the browser tracker (YOLOv8n-pose/MoveNet). It never runs per live frame.

Its output is kept separate from the browser model's output. Differences between
the two are reported as inter-model disagreement, not as accuracy.
"""

import importlib.util
import math
import os
import threading
from datetime import UTC, datetime

import numpy as np

from .assessment import pose_features
from .pose_schema import JOINTS, MODELS, to_coco_arrays

MODEL_ID = 'vitpose-base-simple'
SPEC = MODELS[MODEL_ID]
LOCK = threading.Lock()
MAX_CHECKPOINTS = 24
COMPARED = ('knee_angle', 'hip_angle', 'torso_lean', 'knee_offset', 'hip_height')
_state = {'model': None, 'error': None}


class Unavailable(RuntimeError):
    """ViTPose cannot run on this server (packages missing, disabled or failed to load)."""


def available():
    if os.getenv('WATHBA_VITPOSE', '1') == '0':
        return False, 'ViTPose checks are disabled on this server (WATHBA_VITPOSE=0).'
    missing = [m for m in ('torch', 'transformers', 'PIL') if importlib.util.find_spec(m) is None]
    if missing:
        return False, f"ViTPose needs optional backend packages ({', '.join(missing)}). Install requirements-vitpose.txt."
    if _state['error']:
        return False, _state['error']
    return True, ''


def load():
    ok, reason = available()
    if not ok:
        raise Unavailable(reason)
    with LOCK:
        if _state['model'] is None:
            try:
                import torch
                from transformers import AutoImageProcessor, VitPoseForPoseEstimation
                offline = os.getenv('WATHBA_OFFLINE', '0') == '1'
                processor = AutoImageProcessor.from_pretrained(SPEC['repository'], revision=SPEC['revision'], local_files_only=offline)
                model = VitPoseForPoseEstimation.from_pretrained(SPEC['repository'], revision=SPEC['revision'], local_files_only=offline)
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                _state['model'] = (torch, processor, model.to(device).eval(), device)
            except Exception as exc:  # network, disk or incompatible package versions
                _state['error'] = f'ViTPose could not be loaded on this server: {exc}'[:400]
                raise Unavailable(_state['error']) from exc
    return _state['model']


def unload():
    """Release the model (tests / memory pressure)."""
    with LOCK:
        _state['model'] = None


def box_to_coco(box, width, height):
    """Normalised [x1, y1, x2, y2] -> COCO pixel [x, y, w, h] clipped to the frame."""
    if box is None or len(box) != 4 or not all(math.isfinite(v) for v in box):
        raise ValueError('A person box is required for ViTPose.')
    x1, y1, x2, y2 = (min(max(v, 0.0), 1.0) for v in box)
    x1, x2, y1, y2 = x1 * width, x2 * width, y1 * height, y2 * height
    if x2 - x1 < 8 or y2 - y1 < 8:
        raise ValueError('The person box is too small for ViTPose.')
    return [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]


def to_schema(keypoints_px, scores, width, height):
    """ViTPose pixel output -> wathba.pose/1 named keypoints (outside-frame joints are missing)."""
    result = {}
    for name, (x, y), score in zip(JOINTS, np.asarray(keypoints_px, float), np.asarray(scores, float).reshape(-1)):
        nx, ny = x / width, y / height
        result[name] = {'x': float(nx), 'y': float(ny), 'z': None, 'confidence': float(min(1, max(0, score)))} if 0 <= nx <= 1 and 0 <= ny <= 1 else None
    return result


def estimate(rgb, box):
    """Run ViTPose on one RGB frame for one normalised person box."""
    from PIL import Image
    torch, processor, model, device = load()
    height, width = rgb.shape[:2]
    coco = box_to_coco(box, width, height)
    with LOCK, torch.inference_mode():
        inputs = processor(images=Image.fromarray(rgb), boxes=[[coco]], return_tensors='pt').to(device)
        outputs = model(**inputs)
        pose = processor.post_process_pose_estimation(outputs, boxes=[[coco]])[0][0]
    return to_schema(pose['keypoints'].cpu().numpy(), pose['scores'].cpu().numpy(), width, height)


def checkpoints(session, limit=MAX_CHECKPOINTS):
    """Repetition start and deepest point of each cycle; samples that have a tracked person box."""
    samples = [s for s in session.get('samples', []) if s.get('box') and s.get('points') is not None]
    if not samples:
        return []
    nearest = lambda t: min(samples, key=lambda s: abs(s['time'] - t))
    picks = [(c['rep'], phase, nearest(t)) for c in session.get('cycles', [])
             for phase, t in (('start', c['start']), ('peak', c['peak_time']))]
    if not picks:
        step = max(1, len(samples) // 6)
        picks = [(None, 'sample', s) for s in samples[::step][:6]]
    unique, seen = [], set()
    for rep, phase, s in picks:
        if s['time'] not in seen:
            seen.add(s['time']); unique.append((rep, phase, s))
    return unique[:limit]


def read_frames(video, times):
    import cv2
    cap = cv2.VideoCapture(str(video))
    frames = []
    try:
        for t in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
            ok, frame = cap.read()
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ok else None)
    finally:
        cap.release()
    return frames


def check_session(session, estimator=None):
    """Compare the recording's browser keypoint model with ViTPose at selected frames."""
    estimator = estimator or estimate
    picks = checkpoints(session)
    if not picks:
        raise ValueError('No tracked person boxes are available for a ViTPose check in this recording.')
    side = session['plan']['side']
    frames = read_frames(session['source_video'], [s['time'] for _, _, s in picks])
    browser_model = session.get('keypoint_model')
    rows = []
    for (rep, phase, sample), frame in zip(picks, frames):
        if frame is None:
            continue
        height, width = frame.shape[:2]
        vit = estimator(frame, sample['box'])
        points, scores, reliable = to_coco_arrays(vit, MODEL_ID, width, height)
        vit_features, _ = pose_features(points, scores, side, reliable=reliable)
        browser_features, _ = pose_features(sample['points'], sample['scores'], side, reliable=sample.get('reliable'))
        diff = {k: round(vit_features[k] - browser_features[k], 4) if vit_features.get(k) is not None and browser_features.get(k) is not None else None
                for k in COMPARED}
        rows.append({'rep': rep, 'phase': phase, 'time': sample['time'], 'box': sample['box'],
                     'browser': {'model': browser_model, 'features': {k: browser_features.get(k) for k in COMPARED}},
                     'vitpose': {'features': {k: vit_features.get(k) for k in COMPARED}, 'keypoints': vit},
                     'difference': diff})
    summary = {}
    for k in COMPARED:
        values = [abs(r['difference'][k]) for r in rows if r['difference'][k] is not None]
        summary[k] = {'compared': len(values), 'median_abs_difference': round(float(np.median(values)), 4) if values else None}
    return {'model': MODEL_ID, 'repository': SPEC['repository'], 'revision': SPEC['revision'], 'license': SPEC['license'],
            'browser_model': browser_model, 'created_at': datetime.now(UTC).isoformat(), 'checkpoints': rows, 'summary': summary,
            'note': 'Per-frame 2D image-plane features from each model, computed identically and reported separately. '
                    'hip_height here is per-frame torso-normalised. Agreement between models does not establish accuracy; '
                    'only reference annotations can. These values do not change the session score.'}
