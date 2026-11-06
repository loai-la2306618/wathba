// Real YOLOv8n-pose + MoveNet inference (onnxruntime-node) on frames of a real
// exercise video. Set WATHBA_TEST_VIDEO to a frontal recording of one person
// standing still for the first ~5 s; run scripts/setup_browser_assets.py first.
import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import * as ort from 'onnxruntime-node';
import {NodeBackend, decodeFrames, modelsAvailable, probe} from './helpers.mjs';
import {PoseEngine} from '../../web/pose/engine.js';
import {joint, requireJoints} from '../../web/pose/schema.js';
import {PoseRuntime, YOLO_ID, MOVENET_ID} from '../../web/pose/runtime.js';
import {MODEL_DIR} from './helpers.mjs';
import {join} from 'node:path';

const VIDEO = process.env.WATHBA_TEST_VIDEO;
const skip = !modelsAvailable() ? 'models not downloaded' : !VIDEO || !existsSync(VIDEO) ? 'WATHBA_TEST_VIDEO not set' : false;

let frame;
const standing = () => {
  if (!frame) { const dims = probe(VIDEO); frame = decodeFrames(VIDEO, {fps: 1, ...dims})[5]; }
  return frame;
};

/** Place `image` scaled by `scale` at x offset `dx` on a black canvas of the given width. */
function compose(width, parts) {
  const h = parts[0].image.height, out = new Uint8ClampedArray(width * h * 4);
  for (let i = 3; i < out.length; i += 4) out[i] = 255;
  for (const {image, dx, scale = 1} of parts) {
    const w = Math.floor(image.width * scale), hh = Math.floor(image.height * scale), dy = h - hh;
    for (let y = 0; y < hh; y++) for (let x = 0; x < w; x++) {
      const sx = Math.min(image.width - 1, Math.floor(x / scale)), sy = Math.min(image.height - 1, Math.floor(y / scale));
      const o = ((y + dy) * width + x + dx) * 4, s = (sy * image.width + sx) * 4;
      if (x + dx < width) { out[o] = image.data[s]; out[o + 1] = image.data[s + 1]; out[o + 2] = image.data[s + 2]; }
    }
  }
  return {data: out, width, height: h};
}

const engineFor = image => new PoseEngine({backend: new NodeBackend(ort, {width: image.width, height: image.height})});

test('anatomical left/right on an unmirrored frontal frame; mirrored input would swap anatomy', {skip}, async () => {
  const image = standing(), engine = engineFor(image);
  await engine.init();
  const r = await engine.estimate(image, 0);
  assert.equal(r.status, 'ok');
  const L = joint(r.pose, 'left_hip'), R = joint(r.pose, 'right_hip');
  assert.ok(L && R && L.x > R.x, 'subject faces the camera: anatomical left appears on the image right');
  assert.equal(r.pose.keypoints.left_hip.z, null);
  // Flipping pixels creates a mirror-image person: the model's "left_hip" now sits on the
  // subject's real right hip. This is why inference never uses the mirrored preview.
  const flipped = {...image, data: new Uint8ClampedArray(image.data.length)};
  for (let y = 0; y < image.height; y++) for (let x = 0; x < image.width; x++) {
    const s = (y * image.width + x) * 4, d = (y * image.width + image.width - 1 - x) * 4;
    flipped.data.set(image.data.subarray(s, s + 4), d);
  }
  engine.resetTracking('flip');
  const m = await engine.estimate(flipped, 1);
  assert.ok(Math.abs(joint(m.pose, 'left_hip').x - (1 - R.x)) < .03);
  await engine.dispose();
});

test('multi-person scene: the larger person is selected and a bystander does not take over the track', {skip}, async () => {
  const image = standing();
  const scene = compose(Math.round(image.width * 1.75), [{image, dx: 0}, {image, dx: image.width, scale: .75}]);
  const engine = engineFor(scene);
  await engine.init();
  const first = await engine.estimate(scene, 0);
  assert.equal(first.status, 'ok');
  assert.ok(first.pose.box[2] <= image.width / scene.width + .02, 'selected the larger, left person');
  assert.equal(engine.status().selection.people, 2);
  // The subject leaves; only the smaller bystander remains.
  const alone = compose(Math.round(image.width * 1.75), [{image, dx: image.width, scale: .75}]);
  const subject = first.pose.trackId, results = [];
  for (let t = .2; t < 2.5; t += .2) results.push({t, ...(await engine.estimate(alone, +t.toFixed(1)))});
  assert.notEqual(results[0].status, 'ok', 'loss is reported immediately');
  for (const r of results.filter(r => r.status === 'ok')) {
    assert.notEqual(r.pose.trackId, subject, 'the bystander is never attributed to the subject');
    assert.ok(r.t >= 1, 'a new person is adopted only after the lost timeout');
  }
  await engine.dispose();
});

test('two similar-sized people are ambiguous: no person is chosen', {skip}, async () => {
  const image = standing();
  const scene = compose(image.width * 2, [{image, dx: 0}, {image, dx: image.width}]);
  const engine = engineFor(scene);
  await engine.init();
  const r = await engine.estimate(scene, 0);
  assert.equal(r.status, 'no-person');
  assert.match(r.reason, /similar size/);
  await engine.dispose();
});

test('occluded legs: ankles become unreliable and the squat measurement is unavailable', {skip}, async () => {
  const image = standing(), covered = {...image, data: new Uint8ClampedArray(image.data)};
  const engine = engineFor(image);
  await engine.init();
  const clear = await engine.estimate(image, 0);
  const ankleY = joint(clear.pose, 'left_ankle').y;
  const kneeY = joint(clear.pose, 'left_knee').y;
  const from = Math.floor(((kneeY + ankleY) / 2) * image.height);
  for (let y = from; y < image.height; y++) covered.data.fill(0, y * image.width * 4, (y + 1) * image.width * 4);
  const blocked = await engine.estimate(covered, .2);
  const ok = blocked.status === 'ok' ? requireJoints(blocked.pose, ['left_ankle', 'right_ankle']).ok : false;
  assert.equal(ok, false, 'hidden ankles must not be reported as reliable');
  await engine.dispose();
});

test('model sessions load lazily and are released on dispose', {skip: modelsAvailable() ? false : 'models not downloaded'}, async () => {
  const runtime = new PoseRuntime(ort, {modelSource: (id, file) => join(MODEL_DIR, id, file)});
  assert.equal(runtime.sessions.size, 0);
  await runtime.load([MOVENET_ID]);
  assert.equal(runtime.sessions.size, 1);
  await runtime.dispose();
  assert.equal(runtime.sessions.size, 0);
  const broken = new PoseRuntime(ort, {modelSource: () => join(MODEL_DIR, 'missing.onnx')});
  const status = await broken.load([YOLO_ID]);
  assert.match(status[YOLO_ID], /Could not load/);
});
