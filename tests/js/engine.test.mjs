import test from 'node:test';
import assert from 'node:assert/strict';
import {JOINTS} from '../../web/pose/schema.js';
import {PoseEngine} from '../../web/pose/engine.js';
import {MOVENET_ID, YOLO_ID} from '../../web/pose/runtime.js';

const person = (cx, conf = .9) => Object.fromEntries(JOINTS.map((n, i) => [n, {x: cx + (n.startsWith('left') ? .05 : n.startsWith('right') ? -.05 : 0), y: .1 + i * .045, confidence: conf}]));

/** Scripted backend: each call consults `script(request)`; `hold` makes calls wait for release(). */
class FakeBackend {
  constructor(script) { this.thread = 'fake'; this.script = script; this.calls = []; this.inFlight = 0; this.maxInFlight = 0; this.disposed = false; }
  async init() { return {}; }
  async load(ids) { return Object.fromEntries(ids.map(id => [id, this.loadFailure?.[id] ?? 'ready'])); }
  async run(source, request) {
    this.calls.push(request); this.inFlight++; this.maxInFlight = Math.max(this.maxInFlight, this.inFlight);
    try {
      if (this.hold) await this.hold;
      const r = this.script(request, source) ?? {};
      return {frameId: request.frameId, timestamp: request.timestamp, generation: request.generation, frame: {width: 640, height: 480},
        model: null, keypoints: null, box: request.cropBox, detector: null, selection: null, errors: {}, failed: {}, ...r};
    } finally { this.inFlight--; }
  }
  async dispose() { this.disposed = true; }
}

const detection = (box, keypoints, status = 'new') => ({detector: YOLO_ID, box, selection: {status, reason: status === 'lost' ? 'gone' : '', people: 1}, keypoints, model: MOVENET_ID});

test('YOLO selects the person, MoveNet tracks the crop, YOLO reacquires periodically', async () => {
  const backend = new FakeBackend(req => req.detect ? detection([.3, .05, .7, .95], person(.5), req.previousBox ? 'matched' : 'new') : {model: MOVENET_ID, keypoints: person(.5)});
  const engine = new PoseEngine({backend, config: {reacquireSeconds: 1}});
  await engine.init();
  for (let i = 0; i < 13; i++) {
    const r = await engine.estimate({}, i / 6);
    assert.equal(r.status, 'ok');
    assert.equal(r.pose.model, MOVENET_ID);
    assert.equal(r.pose.trackId, 'person-1');
  }
  assert.deepEqual(backend.calls.map(c => c.detect), [true, false, false, false, false, false, true, false, false, false, false, false, true]);
  assert.ok(backend.calls.slice(1).every(c => c.cropBox), 'MoveNet always receives the selected person crop');
});

test('frames arriving while inference is busy are skipped, never queued', async () => {
  let release; const backend = new FakeBackend(() => ({model: MOVENET_ID, keypoints: person(.5), detector: YOLO_ID, box: [.3, 0, .7, 1], selection: {status: 'new'}}));
  backend.hold = new Promise(r => { release = r; });
  const engine = new PoseEngine({backend});
  await engine.init();
  const first = engine.estimate({}, 0);
  const second = await engine.estimate({}, .1);
  assert.equal(second.status, 'busy');
  release(); await first;
  assert.equal(backend.maxInFlight, 1);
  assert.equal(engine.status().skipped, 1);
});

test('results from before a reset (e.g. a person switch or new recording) are discarded as stale', async () => {
  let release; const backend = new FakeBackend(() => detection([.3, 0, .7, 1], person(.5)));
  backend.hold = new Promise(r => { release = r; });
  const engine = new PoseEngine({backend});
  await engine.init();
  const pending = engine.estimate({}, 0);
  engine.resetTracking('new recording');
  release();
  assert.equal((await pending).status, 'stale');
  assert.equal(engine.status().stale, 1);
});

test('late live results are dropped instead of being shown as current', async () => {
  const backend = new FakeBackend(() => detection([.3, 0, .7, 1], person(.5)));
  backend.hold = new Promise(r => setTimeout(r, 60));
  const engine = new PoseEngine({backend, config: {maxLatencySeconds: .02}});
  await engine.init();
  assert.equal((await engine.estimate({}, 0, {live: true})).status, 'stale');
  backend.hold = null;
  assert.equal((await engine.estimate({}, .2, {live: true})).status, 'ok');
});

test('a bystander is not adopted; after the lost timeout a new track ID and fresh temporal state begin', async () => {
  const events = [];
  let phase = 'me';
  const backend = new FakeBackend(req => {
    if (!req.detect) return phase === 'me' ? {model: MOVENET_ID, keypoints: person(.3)} : {model: MOVENET_ID, keypoints: person(.3, .05)};
    if (phase === 'me') return detection([.2, 0, .4, 1], person(.3));
    // Only someone else is visible now: the runtime reports 'lost' while a previous box exists.
    return req.previousBox ? {detector: YOLO_ID, box: null, selection: {status: 'lost', reason: 'The selected person left the tracked region', people: 1}}
      : detection([.6, 0, .9, 1], person(.75));
  });
  const engine = new PoseEngine({backend, onEvent: e => events.push(e), config: {reacquireSeconds: .5, lostSeconds: 1}});
  await engine.init();
  assert.equal((await engine.estimate({}, 0)).pose.trackId, 'person-1');
  phase = 'other';
  const results = [];
  for (let t = .2; t <= 2.01; t += .2) results.push(await engine.estimate({}, +t.toFixed(2)));
  const statuses = results.map(r => r.status);
  assert.ok(statuses.includes('no-person'), 'tracking loss is reported, not hidden');
  const okAfter = results.filter(r => r.status === 'ok');
  assert.ok(okAfter.every(r => r.pose.trackId !== 'person-1' || r.pose.keypoints.left_hip.confidence < .3),
    'no confident pose is attributed to person-1 after the subject left');
  const switched = okAfter.find(r => r.pose.trackId === 'person-2');
  assert.ok(switched, 'a new person is only adopted as a new track after the lost timeout');
  assert.ok(switched.pose.timestamp >= 1, 'not before lostSeconds');
  assert.ok(events.some(e => e.type === 'reset' && e.reason === 'lost'));
});

test('MoveNet failure falls back to YOLO keypoints and reports degraded status', async () => {
  const statuses = [];
  const backend = new FakeBackend(req => {
    if (req.keypointModel === MOVENET_ID) return {...detection([.3, 0, .7, 1], null), model: null, errors: {[MOVENET_ID]: 'boom'}};
    return {...detection([.3, 0, .7, 1], person(.5), 'new'), model: YOLO_ID};
  });
  const engine = new PoseEngine({backend, onStatus: s => statuses.push(s)});
  await engine.init();
  assert.equal((await engine.estimate({}, 0)).status, 'no-pose');
  const r = await engine.estimate({}, .2);
  assert.equal(r.status, 'ok');
  assert.equal(r.pose.model, YOLO_ID);
  assert.equal(backend.calls.at(-1).detect, true, 'YOLO runs every inference when it supplies the keypoints');
  assert.match(engine.status().degraded.join(' '), /MoveNet is unavailable/);
  assert.equal(engine.status().keypointLabel, 'YOLOv8n-pose');
});

test('YOLO failure keeps MoveNet on the full frame with an explicit unverified track', async () => {
  const backend = new FakeBackend(() => ({model: MOVENET_ID, keypoints: person(.5)}));
  backend.loadFailure = {[YOLO_ID]: 'Could not load'};
  const engine = new PoseEngine({backend});
  await engine.init();
  const r = await engine.estimate({}, 0);
  assert.equal(r.status, 'ok');
  assert.equal(backend.calls[0].detect, false);
  assert.match(r.pose.trackId, /unverified/);
  assert.match(engine.status().degraded.join(' '), /Person detection is unavailable/);
});

test('both models unavailable is an error, not a simulated pose', async () => {
  const backend = new FakeBackend(() => ({}));
  backend.loadFailure = {[YOLO_ID]: 'x', [MOVENET_ID]: 'y'};
  const engine = new PoseEngine({backend});
  await assert.rejects(engine.init(), /No pose model/);
});

test('a failing worker falls back to the page-thread backend', async () => {
  const broken = {thread: 'worker', init: async () => { throw Error('module workers unsupported'); }};
  const fallback = new FakeBackend(() => detection([.3, 0, .7, 1], person(.5)));
  const engine = new PoseEngine({backend: broken, fallbackBackend: () => fallback});
  await engine.init();
  assert.equal(engine.status().thread, 'fake');
  assert.match(engine.status().degraded.join(' '), /page thread/);
  assert.equal((await engine.estimate({}, 0)).status, 'ok');
});

test('seeking backwards resets tracking; dispose releases the backend', async () => {
  const events = [];
  const backend = new FakeBackend(() => detection([.3, 0, .7, 1], person(.5)));
  const engine = new PoseEngine({backend, onEvent: e => events.push(e.reason ?? e.type)});
  await engine.init();
  await engine.estimate({}, 2);
  await engine.estimate({}, 1);
  assert.ok(events.includes('seek'));
  await engine.dispose();
  assert.ok(backend.disposed);
  assert.equal((await engine.estimate({}, 3)).status, 'error');
});
