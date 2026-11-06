"""Model-independent pose schema (wathba.pose/1), shared with web/pose/models.json.

Joints are named COCO-17 keypoints. Coordinates are normalised to the original,
unmirrored frame. Depth is always null: none of the supported models estimate it.
Each model's confidence is its own score, gated by its own threshold; it is not
MediaPipe visibility and is never compared or averaged across models.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1]/'web/pose/models.json'


@lru_cache(maxsize=1)
def config():
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


SCHEMA = config()['schema']
PIPELINE = config()['pipeline']
JOINTS = tuple(config()['joints'])
INDEX = {name: i for i, name in enumerate(JOINTS)}
EDGES = tuple(tuple(e) for e in config()['edges'])
MODELS = config()['models']
CAPABILITIES = dict(config()['capabilities'])
BROWSER_KEYPOINT_MODELS = ('movenet-singlepose-lightning', 'yolov8n-pose')
# Older records produced by the removed MediaPipe engine stay readable.
LEGACY_MEDIAPIPE_ENGINE = 'mediapipe-pose-landmarker-full'
# Index of each COCO-17 joint inside the old 33-landmark MediaPipe records.
_LEGACY_MEDIAPIPE_INDEX = dict(zip(JOINTS, (0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)))


def threshold(model):
    if model not in MODELS:
        raise ValueError(f'Unknown pose model: {model}')
    return float(MODELS[model]['keypointThreshold'])


def joint_index(name):
    return INDEX[name]


def unavailable_measurements(capabilities=None):
    capabilities = capabilities or CAPABILITIES
    return [{'id': key, 'label': spec['label'], 'reason': spec['reason']}
            for key, spec in config()['unsupportedMeasurements'].items() if not capabilities.get(spec['requires'])]


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_keypoints(keypoints):
    """Return {joint: {x, y, confidence} | None} or raise ValueError."""
    if not isinstance(keypoints, dict):
        raise ValueError('Pose keypoints must be a joint-name mapping.')
    unknown = set(keypoints) - set(JOINTS)
    if unknown:
        raise ValueError(f'Unsupported joints for COCO-17 models: {sorted(unknown)[:4]}')
    result = {}
    for name in JOINTS:
        k = keypoints.get(name)
        if k is None:
            result[name] = None
            continue
        if not isinstance(k, dict):
            raise ValueError('Invalid body-tracking coordinates.')
        x, y, c = k.get('x'), k.get('y'), k.get('confidence')
        if not (_finite(x) and _finite(y) and _finite(c)) or abs(x) > 2 or abs(y) > 2 or not 0 <= c <= 1:
            raise ValueError('Invalid body-tracking coordinates.')
        if k.get('z') is not None:
            raise ValueError('These 2D models provide no depth; z must be null.')
        result[name] = {'x': float(x), 'y': float(y), 'z': None, 'confidence': float(c)}
    return result


def to_coco_arrays(keypoints, model, width, height):
    """Pixel points (COCO-17 order), raw model scores and per-joint reliability.

    Missing joints become NaN points with score 0 and are never reliable.
    """
    limit = threshold(model)
    points, scores, reliable = [], [], []
    for name in JOINTS:
        k = keypoints.get(name)
        if k is None:
            points.append([math.nan, math.nan])
            scores.append(0.0)
            reliable.append(False)
            continue
        inside = -.05 <= k['x'] <= 1.05 and -.05 <= k['y'] <= 1.05
        points.append([k['x'] * width, k['y'] * height])
        scores.append(round(k['confidence'], 4))
        reliable.append(bool(inside and k['confidence'] >= limit))
    return points, scores, reliable


def legacy_mediapipe_row(row):
    """Convert one stored 33-landmark MediaPipe row to the named schema for replay.

    Only the 17 COCO-equivalent landmarks are kept; MediaPipe visibility is
    carried as that legacy record's confidence and labelled as such.
    """
    landmarks = row.get('landmarks') or []
    keypoints = None
    if len(landmarks) == 33:
        keypoints = {name: {'x': landmarks[i]['x'], 'y': landmarks[i]['y'], 'z': None,
                            'confidence': max(0.0, min(1.0, float(landmarks[i].get('visibility', 0))))}
                     for name, i in _LEGACY_MEDIAPIPE_INDEX.items()}
    return {'time': row['time'], 'model': 'mediapipe-legacy-record', 'keypoints': keypoints,
            'threshold': .45, 'trackId': None, 'box': None}


def replay_rows(session):
    """Named-joint rows for the frontend renderer, for new and legacy sessions."""
    rows = session.get('browser_landmarks', [])
    if session.get('pose_engine') == LEGACY_MEDIAPIPE_ENGINE:
        return [legacy_mediapipe_row(r) for r in rows]
    return [{**r, 'threshold': threshold(r['model']) if r.get('model') in MODELS else None} for r in rows]
