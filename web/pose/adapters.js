// Pure, framework-free model adapters: preprocessing, output decoding and the
// coordinate transforms between model input, crop and original frame. No DOM or
// runtime dependency, so the same code runs in the worker, main thread and Node.
import {JOINTS, MODELS} from './schema.js';

const YOLO = MODELS['yolov8n-pose'];
const MOVENET = MODELS['movenet-singlepose-lightning'];

/**
 * Bilinear sample of `rect` (source pixels; may extend outside the image) into
 * an outW x outH grid. Outside-image samples are zero padding.
 * image: {data: RGBA Uint8ClampedArray|Uint8Array, width, height}
 */
export function sampleRegion(image, rect, outW, outH, write) {
  const {data, width, height} = image;
  const sx = rect.w / outW, sy = rect.h / outH;
  // Per-column source offsets and weights, computed once (no per-pixel allocation).
  // An offset of -1 marks a column outside the image: it contributes zero (padding).
  const left = new Int32Array(outW), right = new Int32Array(outW), wxs = new Float32Array(outW);
  for (let ox = 0; ox < outW; ox++) {
    const fx = rect.x + (ox + .5) * sx - .5, x0 = Math.floor(fx);
    wxs[ox] = fx - x0;
    left[ox] = x0 >= 0 && x0 < width ? x0 * 4 : -1;
    right[ox] = x0 + 1 >= 0 && x0 + 1 < width ? (x0 + 1) * 4 : -1;
  }
  for (let oy = 0; oy < outH; oy++) {
    const fy = rect.y + (oy + .5) * sy - .5, y0 = Math.floor(fy), wy = fy - y0;
    const top = y0 >= 0 && y0 < height ? y0 * width * 4 : -1;
    const bottom = y0 + 1 >= 0 && y0 + 1 < height ? (y0 + 1) * width * 4 : -1;
    const row = oy * outW;
    for (let ox = 0; ox < outW; ox++) {
      const wx = wxs[ox], l = left[ox], rt = right[ox];
      let r = 0, g = 0, b = 0, w, i;
      if (top >= 0) {
        if (l >= 0 && (w = (1 - wx) * (1 - wy)) !== 0) { i = top + l; r += data[i] * w; g += data[i + 1] * w; b += data[i + 2] * w; }
        if (rt >= 0 && (w = wx * (1 - wy)) !== 0) { i = top + rt; r += data[i] * w; g += data[i + 1] * w; b += data[i + 2] * w; }
      }
      if (bottom >= 0) {
        if (l >= 0 && (w = (1 - wx) * wy) !== 0) { i = bottom + l; r += data[i] * w; g += data[i + 1] * w; b += data[i + 2] * w; }
        if (rt >= 0 && (w = wx * wy) !== 0) { i = bottom + rt; r += data[i] * w; g += data[i + 1] * w; b += data[i + 2] * w; }
      }
      write(row + ox, r, g, b);
    }
  }
}

// ---------------------------------------------------------------- YOLOv8-pose
/** Stretch-resize the full frame to 640x640, RGB/255, NCHW (per preprocessor_config.json). */
export function yoloPreprocess(image) {
  const {width: W, height: H} = YOLO.input, plane = W * H, out = new Float32Array(3 * plane), s = YOLO.input.rescale;
  sampleRegion(image, {x: 0, y: 0, w: image.width, h: image.height}, W, H, (i, r, g, b) => {
    out[i] = r * s; out[plane + i] = g * s; out[2 * plane + i] = b * s;
  });
  return {data: out, dims: [1, 3, H, W]};
}

export function iou(a, b) {
  const w = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
  const h = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const inter = w * h, union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
  return union > 0 ? inter / union : 0;
}

export function nms(detections, threshold) {
  const kept = [];
  for (const d of [...detections].sort((a, b) => b.score - a.score)) {
    if (kept.every(k => iou(k.box, d.box) <= threshold)) kept.push(d);
  }
  return kept;
}

const inFrame = (x, y) => x >= 0 && x <= 1 && y >= 0 && y <= 1;

/**
 * Decode output0 [1, 56, N]. Because the input was stretched (no padding),
 * dividing by the input size gives coordinates normalised to the original frame.
 */
export function decodeYolo(output, dims, {personThreshold = YOLO.personThreshold, nmsIou = YOLO.nmsIou} = {}) {
  const [, channels, count] = dims;
  if (channels !== 5 + 3 * JOINTS.length) throw Error(`Unexpected YOLO pose output channels: ${channels}`);
  const {width: W, height: H} = YOLO.input, at = (c, i) => output[c * count + i];
  const candidates = [];
  for (let i = 0; i < count; i++) {
    const score = at(4, i);
    if (score < personThreshold) continue;
    const cx = at(0, i) / W, cy = at(1, i) / H, w = at(2, i) / W, h = at(3, i) / H;
    const keypoints = {};
    JOINTS.forEach((name, j) => {
      const x = at(5 + 3 * j, i) / W, y = at(6 + 3 * j, i) / H, confidence = at(7 + 3 * j, i);
      keypoints[name] = inFrame(x, y) ? {x, y, confidence} : null;
    });
    candidates.push({box: [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], score, keypoints});
  }
  return nms(candidates, nmsIou);
}

// -------------------------------------------------------------------- MoveNet
/** Square crop around a normalised person box, in source pixels. May extend past the frame (padded). */
export function movenetCrop(box, image, margin = MOVENET.cropMargin) {
  const [x1, y1, x2, y2] = box;
  const cx = (x1 + x2) / 2 * image.width, cy = (y1 + y2) / 2 * image.height;
  const side = Math.max((x2 - x1) * image.width, (y2 - y1) * image.height) * (1 + margin);
  return {x: cx - side / 2, y: cy - side / 2, w: side, h: side};
}

/** Full-frame square (letterbox-style padding) when no person box is available. */
export function fullFrameCrop(image) {
  const side = Math.max(image.width, image.height);
  return {x: (image.width - side) / 2, y: (image.height - side) / 2, w: side, h: side};
}

export function movenetPreprocess(image, rect) {
  const {width: W, height: H} = MOVENET.input, out = new Int32Array(W * H * 3);
  sampleRegion(image, rect, W, H, (i, r, g, b) => {
    out[3 * i] = Math.round(r); out[3 * i + 1] = Math.round(g); out[3 * i + 2] = Math.round(b);
  });
  return {data: out, dims: [1, H, W, 3]};
}

/** output_0 [1,1,17,3] = (y, x, score) in crop units -> original-frame normalised coordinates. */
export function decodeMovenet(output, rect, image) {
  if (output.length !== JOINTS.length * 3) throw Error(`Unexpected MoveNet output length: ${output.length}`);
  const keypoints = {};
  JOINTS.forEach((name, j) => {
    const y = (rect.y + output[3 * j] * rect.h) / image.height;
    const x = (rect.x + output[3 * j + 1] * rect.w) / image.width;
    // A joint placed in the zero-padded area is not observed in the frame.
    keypoints[name] = inFrame(x, y) ? {x, y, confidence: output[3 * j + 2]} : null;
  });
  return keypoints;
}

// ---------------------------------------------------------- person selection
/** Box around reliable keypoints, expanded to include head/feet; null when too few joints. */
export function boxFromKeypoints(keypoints, threshold, {minJoints = 6, margin = .2} = {}) {
  const pts = Object.values(keypoints).filter(k => k && k.confidence >= threshold);
  if (pts.length < minJoints) return null;
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
  let [x1, y1, x2, y2] = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  const w = Math.max(x2 - x1, .02), h = Math.max(y2 - y1, .02);
  x1 -= w * margin; x2 += w * margin; y1 -= h * margin; y2 += h * margin * .6;
  return [x1, y1, x2, y2];
}

const area = b => (b[2] - b[0]) * (b[3] - b[1]);

/**
 * Keep the same subject. Without a previous box, pick the largest person only
 * when unambiguous; with one, never jump to a non-overlapping bystander.
 */
export function selectPerson(detections, previousBox = null, {minIou = .15, ambiguity = 1.3} = {}) {
  if (!detections.length) return {detection: null, status: 'none', reason: 'No person detected'};
  if (previousBox) {
    let best = null, bestIou = 0;
    for (const d of detections) { const v = iou(d.box, previousBox); if (v > bestIou) { best = d; bestIou = v; } }
    return bestIou >= minIou ? {detection: best, status: 'matched', reason: ''}
      : {detection: null, status: 'lost', reason: 'The selected person left the tracked region'};
  }
  const sorted = [...detections].sort((a, b) => area(b.box) - area(a.box));
  if (sorted.length > 1 && area(sorted[0].box) < area(sorted[1].box) * ambiguity) {
    return {detection: null, status: 'ambiguous', reason: 'Several people of similar size are visible. Only the person being assessed should be in view.'};
  }
  return {detection: sorted[0], status: 'new', reason: ''};
}

// ------------------------------------------------------------------ smoothing
class OneEuro {
  constructor(minCutoff, beta, dCutoff) { Object.assign(this, {minCutoff, beta, dCutoff}); this.reset(); }
  reset() { this.x = null; this.dx = 0; this.t = null; }
  static alpha(cutoff, dt) { const tau = 1 / (2 * Math.PI * cutoff); return 1 / (1 + tau / dt); }
  filter(value, t) {
    if (this.x === null || t <= this.t) { this.x = value; this.t = t; this.dx = 0; return value; }
    const dt = t - this.t, dx = (value - this.x) / dt;
    this.dx += OneEuro.alpha(this.dCutoff, dt) * (dx - this.dx);
    this.x += OneEuro.alpha(this.minCutoff + this.beta * Math.abs(this.dx), dt) * (value - this.x);
    this.t = t;
    return this.x;
  }
}

/**
 * One-Euro smoothing per joint for display and live counting. A joint that is
 * missing or below threshold resets its filter and is passed through as-is, so
 * tracking loss is never hidden by holding or extrapolating an old position.
 */
export class PoseSmoother {
  constructor({minCutoff = 1.2, beta = .4, dCutoff = 1, maxGap = .5} = {}) {
    this.options = {minCutoff, beta, dCutoff}; this.maxGap = maxGap; this.filters = new Map(); this.last = null;
  }
  reset() { this.filters.clear(); this.last = null; }
  apply(pose, threshold) {
    if (this.last !== null && (pose.timestamp - this.last > this.maxGap || pose.timestamp <= this.last)) this.reset();
    this.last = pose.timestamp;
    const keypoints = {};
    for (const name of JOINTS) {
      const k = pose.keypoints[name];
      let f = this.filters.get(name);
      if (!k || k.confidence < threshold) { f?.x?.reset(); f?.y?.reset(); keypoints[name] = k; continue; }
      if (!f) { f = {x: new OneEuro(...Object.values(this.options)), y: new OneEuro(...Object.values(this.options))}; this.filters.set(name, f); }
      keypoints[name] = {...k, x: f.x.filter(k.x, pose.timestamp), y: f.y.filter(k.y, pose.timestamp)};
    }
    return {...pose, keypoints, smoothed: true};
  }
}
