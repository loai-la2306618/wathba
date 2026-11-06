// Model-independent pose schema shared by every adapter, the renderer and the
// exercise rules. Joints are addressed by anatomical name, never by a model's
// array index. Coordinates are normalised to the ORIGINAL, unmirrored frame.
import CONFIG from './models.json' with {type: 'json'};

export {CONFIG};
export const SCHEMA = CONFIG.schema;
export const PIPELINE = CONFIG.pipeline;
export const JOINTS = Object.freeze([...CONFIG.joints]);
export const EDGES = Object.freeze(CONFIG.edges.map(e => Object.freeze([...e])));
export const MODELS = CONFIG.models;
export const CAPABILITIES = Object.freeze({...CONFIG.capabilities});
// Anatomical left/right: a model's "left_knee" is the subject's left knee.
export const MIRROR_PAIR = Object.freeze(Object.fromEntries(JOINTS.map(n => [n,
  n.startsWith('left_') ? 'right_' + n.slice(5) : n.startsWith('right_') ? 'left_' + n.slice(6) : n])));

/** Per-model keypoint confidence threshold. Scores are not comparable across models. */
export function keypointThreshold(model) {
  const spec = MODELS[model];
  if (!spec) throw Error(`Unknown pose model: ${model}`);
  return spec.keypointThreshold;
}

/**
 * Build a pose record. `keypoints` maps joint name -> {x, y, confidence} with
 * x/y normalised to the original frame, or null when the model did not produce
 * an observable joint (e.g. predicted outside the frame).
 */
export function makePose({frameId, timestamp, trackId = null, model, width, height, keypoints, box = null, detector = null}) {
  if (!MODELS[model]) throw Error(`Unknown pose model: ${model}`);
  const named = {};
  for (const name of JOINTS) {
    const k = keypoints?.[name];
    named[name] = k && Number.isFinite(k.x) && Number.isFinite(k.y) && Number.isFinite(k.confidence)
      ? {x: k.x, y: k.y, z: null, confidence: k.confidence} : null;
  }
  return {
    schema: SCHEMA, frameId, timestamp, trackId, model, detector,
    frame: {width, height},
    coordinateSpace: 'normalized-original-frame',
    mirrored: false,
    capabilities: {...CAPABILITIES},
    confidenceKind: MODELS[model].confidenceKind,
    box, keypoints: named,
  };
}

/** A joint usable for measurement: produced, inside the frame and above the model's threshold. */
export function joint(pose, name, {margin = .05} = {}) {
  const k = pose?.keypoints?.[name];
  if (!k) return null;
  if (k.confidence < keypointThreshold(pose.model)) return null;
  if (k.x < -margin || k.x > 1 + margin || k.y < -margin || k.y > 1 + margin) return null;
  return k;
}

export function requireJoints(pose, names) {
  const missing = names.filter(n => !joint(pose, n));
  return {ok: !missing.length, missing};
}

/** Explicit capability gate for measurements the COCO-17 models cannot support. */
export function capabilityCheck(measurement, capabilities = CAPABILITIES) {
  const unsupported = CONFIG.unsupportedMeasurements[measurement];
  if (unsupported) {
    return capabilities[unsupported.requires]
      ? {available: true, reason: ''}
      : {available: false, label: unsupported.label, reason: unsupported.reason};
  }
  if (CONFIG.measurementRequirements[measurement]) return {available: true, reason: '', joints: CONFIG.measurementRequirements[measurement]};
  return {available: false, reason: `Unknown measurement: ${measurement}`};
}

export function unavailableMeasurements(capabilities = CAPABILITIES) {
  return Object.keys(CONFIG.unsupportedMeasurements)
    .map(id => ({id, ...capabilityCheck(id, capabilities)}))
    .filter(r => !r.available);
}

/**
 * Display transform only. A mirrored preview flips x for drawing, but the
 * joint keeps its anatomical name: the subject's left knee stays "left_knee".
 */
export function toDisplay(point, mirrored) {
  return point ? {...point, x: mirrored ? 1 - point.x : point.x} : null;
}

/** Normalised point -> pixel coordinates of the original frame. */
export function toPixels(point, frame) {
  return point ? [point.x * frame.width, point.y * frame.height] : null;
}
