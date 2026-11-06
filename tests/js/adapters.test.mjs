import test from 'node:test';
import assert from 'node:assert/strict';
import {JOINTS, MIRROR_PAIR, capabilityCheck, joint, makePose, requireJoints, toDisplay, unavailableMeasurements} from '../../web/pose/schema.js';
import {PoseSmoother, boxFromKeypoints, decodeMovenet, decodeYolo, fullFrameCrop, iou, movenetCrop, movenetPreprocess, nms, sampleRegion, selectPerson, yoloPreprocess} from '../../web/pose/adapters.js';

const close = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) <= eps, `${a} != ${b}`);

/** RGBA test image with a single bright pixel at (px, py). */
function dotImage(width, height, px, py) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 3; i < data.length; i += 4) data[i] = 255;
  data.set([255, 128, 64], (py * width + px) * 4);
  return {data, width, height};
}

test('sampling maps crop pixels to the right source location and pads outside the frame', () => {
  const image = dotImage(10, 10, 7, 2);
  const seen = [];
  sampleRegion(image, {x: 5, y: 0, w: 5, h: 5}, 5, 5, (i, r) => { if (r > 0) seen.push(i); });
  assert.deepEqual(seen, [2 * 5 + 2]); // (7-5, 2-0)
  const padded = [];
  sampleRegion(image, {x: -10, y: -10, w: 10, h: 10}, 4, 4, (i, r, g, b) => padded.push(r + g + b));
  assert.ok(padded.every(v => v === 0), 'pixels outside the image must be zero padding');
});

test('YOLO preprocessing stretches to 640x640 NCHW and rescales by 1/255', () => {
  const {data, dims} = yoloPreprocess(dotImage(64, 32, 32, 16));
  assert.deepEqual(dims, [1, 3, 640, 640]);
  // Source pixel (32,16) of 64x32 lands at input (x 320..329, y 320..339) after stretching.
  const at = 330 * 640 + 325, R = data.subarray(0, 640 * 640);
  const peak = R.reduce((best, v, i) => v > R[best] ? i : best, 0);
  assert.ok(Math.abs(peak % 640 - 324.5) <= 6 && Math.abs(Math.floor(peak / 640) - 329.5) <= 11, `peak at ${peak % 640},${Math.floor(peak / 640)}`);
  close(data[at], 1, .1);
  close(data[640 * 640 + at] / data[at], 128 / 255, 1e-6);
  close(data[2 * 640 * 640 + at] / data[at], 64 / 255, 1e-6);
  assert.equal(data[0], 0);
});

function yoloTensor(people) {
  const n = 8400, out = new Float32Array(56 * n);
  people.forEach((p, i) => {
    const set = (c, v) => { out[c * n + i] = v; };
    set(0, p.cx); set(1, p.cy); set(2, p.w); set(3, p.h); set(4, p.score);
    JOINTS.forEach((name, j) => { const k = p.kp?.[name] ?? [p.cx, p.cy, .9]; set(5 + 3 * j, k[0]); set(6 + 3 * j, k[1]); set(7 + 3 * j, k[2]); });
  });
  return {data: out, dims: [1, 56, n]};
}

test('YOLO decoding normalises boxes/keypoints to the original frame and suppresses duplicates', () => {
  const {data, dims} = yoloTensor([
    {cx: 320, cy: 320, w: 128, h: 512, score: .9, kp: {left_knee: [384, 448, .8], right_ankle: [700, 600, .9]}},
    {cx: 322, cy: 318, w: 130, h: 510, score: .7},
    {cx: 100, cy: 300, w: 60, h: 200, score: .3},
  ]);
  const people = decodeYolo(data, dims);
  assert.equal(people.length, 1);
  const [x1, y1, x2, y2] = people[0].box;
  close(x1, .4); close(y1, .1); close(x2, .6); close(y2, .9);
  close(people[0].keypoints.left_knee.x, .6); close(people[0].keypoints.left_knee.y, .7);
  close(people[0].keypoints.left_knee.confidence, .8, 1e-6);
  assert.equal(people[0].keypoints.right_ankle, null, 'a keypoint outside the frame is missing, not clamped');
  assert.throws(() => decodeYolo(new Float32Array(10), [1, 5, 2]));
});

test('NMS keeps the higher score and IoU is symmetric', () => {
  const a = {box: [0, 0, 1, 1], score: .5}, b = {box: [0, 0, 1, .9], score: .8}, c = {box: [2, 2, 3, 3], score: .6};
  assert.deepEqual(nms([a, b, c], .5), [b, c]);
  close(iou([0, 0, 2, 2], [1, 1, 3, 3]), 1 / 7);
  close(iou([1, 1, 3, 3], [0, 0, 2, 2]), 1 / 7);
});

test('MoveNet crop is square around the box and decodes back to original-frame coordinates', () => {
  const image = {width: 400, height: 800};
  const rect = movenetCrop([.25, .25, .75, .75], image, .25);
  close(rect.w, 500); close(rect.h, 500); close(rect.x, -50); close(rect.y, 150);
  const out = new Float32Array(17 * 3);
  const k = JOINTS.indexOf('left_hip'), r = JOINTS.indexOf('right_ankle');
  out.set([.5, .5, .9], 3 * k);      // (y, x, score) in crop units -> centre of crop
  out.set([.2, .05, .8], 3 * r);     // x = -50 + .05*500 = -25 px -> outside the frame
  const kp = decodeMovenet(out, rect, image);
  close(kp.left_hip.x, .5); close(kp.left_hip.y, .5); close(kp.left_hip.confidence, .9, 1e-6);
  assert.equal(kp.right_ankle, null, 'joint predicted in padding is not observed');
  const full = fullFrameCrop(image);
  assert.deepEqual(full, {x: -200, y: 0, w: 800, h: 800});
});

test('MoveNet preprocessing is int32 NHWC with zero padding', () => {
  const image = dotImage(4, 4, 0, 0);
  const {data, dims} = movenetPreprocess(image, {x: 0, y: 0, w: 192, h: 192});
  assert.deepEqual(dims, [1, 192, 192, 3]);
  assert.ok(data instanceof Int32Array);
  assert.equal(data[0], 255); assert.equal(data[1], 128); assert.equal(data[2], 64);
  assert.equal(data[3 * (191 * 192 + 191)], 0, 'outside the 4x4 image is padding');
});

test('anatomical names survive a mirrored display transform', () => {
  const pose = makePose({frameId: 1, timestamp: 0, model: 'movenet-singlepose-lightning', width: 640, height: 480,
    keypoints: {left_knee: {x: .7, y: .6, confidence: .9}, right_knee: {x: .3, y: .6, confidence: .9}}});
  const shown = toDisplay(pose.keypoints.left_knee, true);
  close(shown.x, .3);
  // Data stays in the original frame: the subject's left knee is still left_knee at x=.7.
  close(pose.keypoints.left_knee.x, .7);
  assert.equal(pose.mirrored, false);
  assert.equal(MIRROR_PAIR.left_knee, 'right_knee');
  assert.equal(MIRROR_PAIR.nose, 'nose');
});

test('schema marks depth missing, gates by per-model thresholds and never invents joints', () => {
  const kp = {left_hip: {x: .5, y: .5, confidence: .4}};
  const movenet = makePose({frameId: 1, timestamp: 0, model: 'movenet-singlepose-lightning', width: 1, height: 1, keypoints: kp});
  const yolo = makePose({frameId: 1, timestamp: 0, model: 'yolov8n-pose', width: 1, height: 1, keypoints: kp});
  assert.equal(movenet.keypoints.left_hip.z, null);
  assert.equal(movenet.capabilities.depth, false);
  assert.ok(joint(movenet, 'left_hip'), '0.4 passes MoveNet threshold 0.3');
  assert.equal(joint(yolo, 'left_hip'), null, '0.4 fails YOLO threshold 0.5');
  assert.equal(movenet.keypoints.left_knee, null);
  assert.equal(Object.keys(movenet.keypoints).length, 17);
  assert.ok(!('left_heel' in movenet.keypoints));
  assert.deepEqual(requireJoints(movenet, ['left_hip', 'left_knee']), {ok: false, missing: ['left_knee']});
  assert.throws(() => makePose({model: 'mediapipe', keypoints: {}}));
});

test('measurements needing depth or foot landmarks are explicitly unavailable', () => {
  const heel = capabilityCheck('heel_toe_contact');
  assert.equal(heel.available, false);
  assert.match(heel.reason, /heel or toe/);
  assert.equal(capabilityCheck('knee_flexion_3d').available, false);
  assert.equal(capabilityCheck('hip_height').available, true);
  assert.ok(unavailableMeasurements().some(m => m.id === 'depth'));
});

test('person selection does not switch to a bystander and flags ambiguity', () => {
  const me = {box: [.1, .1, .3, .9]}, big = {box: [.5, 0, 1, 1]}, twin = {box: [.6, .1, .8, .9]};
  assert.equal(selectPerson([me, big]).detection, big);
  assert.equal(selectPerson([me, twin]).status, 'ambiguous');
  assert.equal(selectPerson([big, {box: [.11, .1, .31, .9]}], me.box).detection.box[0], .11);
  assert.equal(selectPerson([big], me.box).status, 'lost');
  assert.equal(selectPerson([]).status, 'none');
});

test('keypoint box needs enough reliable joints', () => {
  const kp = Object.fromEntries(JOINTS.map((n, i) => [n, {x: .4 + i * .01, y: .1 + i * .04, confidence: i < 4 ? .9 : .1}]));
  assert.equal(boxFromKeypoints(kp, .3), null);
  for (const n of JOINTS) kp[n].confidence = .9;
  const box = boxFromKeypoints(kp, .3);
  assert.ok(box[0] < .4 && box[2] > .56 && box[1] < .1 && box[3] > .74);
});

test('smoothing reduces jitter but passes through low-confidence joints without holding them', () => {
  const smoother = new PoseSmoother();
  let out;
  for (let i = 0; i < 10; i++) {
    out = smoother.apply(makePose({frameId: i, timestamp: i / 10, model: 'movenet-singlepose-lightning', width: 1, height: 1,
      keypoints: {left_hip: {x: .5 + (i % 2 ? .02 : -.02), y: .5, confidence: .9}, left_knee: {x: .4, y: .7, confidence: i === 9 ? .1 : .9}}}), .3);
  }
  assert.ok(Math.abs(out.keypoints.left_hip.x - .5) < .02, 'jitter is attenuated');
  assert.equal(out.keypoints.left_knee.confidence, .1, 'unreliable joint keeps its low confidence');
  const after = smoother.apply(makePose({frameId: 99, timestamp: 5, model: 'movenet-singlepose-lightning', width: 1, height: 1,
    keypoints: {left_hip: {x: .9, y: .5, confidence: .9}}}), .3);
  close(after.keypoints.left_hip.x, .9, 1e-9); // a gap resets the filter: no lag from the old position
});
