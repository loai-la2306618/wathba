import test from 'node:test';
import assert from 'node:assert/strict';
import {makePose} from '../../web/pose/schema.js';
import {measurements, compareParts, edgePart} from '../../web/motion-coach.js';

const pose = (kp, model = 'movenet-singlepose-lightning') => makePose({frameId: 1, timestamp: 0, model, width: 400, height: 800, keypoints: kp});
const leg = c => ({left_hip: {x: .45, y: .5, confidence: c}, left_knee: {x: .40, y: .7, confidence: c}, left_ankle: {x: .45, y: .9, confidence: c},
  left_shoulder: {x: .45, y: .2, confidence: c}});

test('exercise rules use named joints and 2D pixel geometry', () => {
  const v = measurements(pose(leg(.9)));
  // knee 20 px off a vertical 320 px hip-ankle line -> 20/320
  assert.ok(Math.abs(v.leftKnee - 20 / 320) < 1e-9);
  assert.ok(Math.abs(v.trunk) < 1e-9);
  assert.equal(v.rightKnee, undefined, 'missing right leg is not measured');
  assert.equal(edgePart('left_knee', 'left_ankle'), 'leftKnee');
  assert.equal(edgePart('left_shoulder', 'left_hip'), 'trunk');
});

test('unreliable joints make a part grey instead of guessing', () => {
  assert.deepEqual(measurements(pose(leg(.4), 'yolov8n-pose')), {}, '0.4 is below YOLO threshold');
  assert.equal(compareParts(measurements(pose(leg(.2))), {leftKnee: .06}).leftKnee.status, 'grey');
  assert.equal(compareParts(measurements(pose(leg(.9))), {leftKnee: .06}).leftKnee.status, 'green');
});
