// Coordinates the browser pose models for one selected person.
//   YOLOv8n-pose  -> person detection, first pose, periodic reacquisition
//   MoveNet       -> continuous keypoints on the selected person's crop
// At most one inference is in flight; frames arriving while busy are skipped
// (no queue). Results from an older generation, an older frame or (live) that
// arrive too late are discarded.
import {MODELS, keypointThreshold, makePose} from './schema.js';
import {PoseSmoother, boxFromKeypoints, iou} from './adapters.js';
import {MOVENET_ID, YOLO_ID} from './runtime.js';

const MAX_SIDE = 640;
const clock = () => (globalThis.performance ?? Date).now();
export const DEFAULTS = Object.freeze({maxHz: 15, reacquireSeconds: 1, lostSeconds: 1.5, maxLatencySeconds: 1, timeoutSeconds: 30});

async function captureFrame(source) {
  const w = source.videoWidth || source.width, h = source.videoHeight || source.height;
  if (!w || !h) throw Error('The video frame is not ready yet.');
  const scale = Math.min(1, MAX_SIDE / Math.max(w, h));
  const bitmap = await createImageBitmap(source, {resizeWidth: Math.round(w * scale), resizeHeight: Math.round(h * scale), resizeQuality: 'medium'});
  return {bitmap, frame: {width: w, height: h}};
}

/** Inference in a module Web Worker, off the UI thread. */
export class WorkerBackend {
  constructor(url = '/static/pose/worker.js') { this.url = url; this.thread = 'worker'; this.pending = new Map(); this.next = 0; }
  async init() {
    this.worker = new Worker(this.url, {type: 'module'});
    this.worker.onmessage = ({data}) => { const p = this.pending.get(data.id); if (!p) return; this.pending.delete(data.id); clearTimeout(p.timer); data.error ? p.reject(Error(data.error)) : p.resolve(data.payload); };
    this.worker.onerror = event => { for (const p of this.pending.values()) { clearTimeout(p.timer); p.reject(Error(event.message || 'Pose worker failed.')); } this.pending.clear(); event.preventDefault?.(); };
    return this.call('init', {});
  }
  call(type, payload, transfer = [], timeout = DEFAULTS.timeoutSeconds) {
    const id = ++this.next;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(Error('Pose inference timed out.')); }, timeout * 1000);
      this.pending.set(id, {resolve, reject, timer});
      this.worker.postMessage({id, type, ...payload}, transfer);
    });
  }
  load(ids) { return this.call('load', {ids}, [], 120); }
  async run(source, request) {
    const {bitmap, frame} = await captureFrame(source);
    const result = await this.call('run', {bitmap, request}, [bitmap]);
    return {...result, frame};
  }
  async dispose() {
    try { await this.call('dispose', {}, [], 5); } catch { /* worker may already be gone */ }
    this.worker?.terminate(); this.worker = null;
  }
}

/** Same runtime on the main thread, for browsers without module workers/OffscreenCanvas. */
export class MainThreadBackend {
  constructor() { this.thread = 'main'; }
  async init() {
    const [ort, {PoseRuntime}] = await Promise.all([import('/vendor/ort/ort.wasm.min.mjs'), import('./runtime.js')]);
    ort.env.wasm.wasmPaths = '/vendor/ort/';
    ort.env.wasm.numThreads = globalThis.crossOriginIsolated ? Math.max(1, Math.min(4, (navigator.hardwareConcurrency || 2) - 1)) : 1;
    this.runtime = new PoseRuntime(ort, {modelSource: (id, file) => `/vendor/models/${id}/${file}`, sessionOptions: {executionProviders: ['wasm']}});
    this.canvas = document.createElement('canvas'); this.ctx = this.canvas.getContext('2d', {willReadFrequently: true});
    return {threads: ort.env.wasm.numThreads};
  }
  load(ids) { return this.runtime.load(ids); }
  async run(source, request) {
    const w = source.videoWidth || source.width, h = source.videoHeight || source.height, scale = Math.min(1, MAX_SIDE / Math.max(w, h));
    this.canvas.width = Math.round(w * scale); this.canvas.height = Math.round(h * scale);
    this.ctx.drawImage(source, 0, 0, this.canvas.width, this.canvas.height);
    const pixels = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
    const result = await this.runtime.run({data: pixels.data, width: pixels.width, height: pixels.height}, request);
    return {...result, failed: {...this.runtime.failed}, frame: {width: w, height: h}};
  }
  async dispose() { await this.runtime?.dispose(); this.runtime = null; }
}

export function defaultBackend() {
  const workers = typeof Worker !== 'undefined' && typeof OffscreenCanvas !== 'undefined' && typeof createImageBitmap !== 'undefined';
  return workers ? new WorkerBackend() : new MainThreadBackend();
}

export class PoseEngine {
  constructor({backend = defaultBackend(), fallbackBackend = () => new MainThreadBackend(), config = {}, onStatus = () => {}, onEvent = () => {}} = {}) {
    this.backend = backend; this.fallbackBackend = fallbackBackend;
    this.config = {...DEFAULTS, ...Object.fromEntries(Object.entries(config).filter(([, v]) => Number.isFinite(v) && v > 0))};
    this.onStatus = onStatus; this.onEvent = onEvent;
    this.smoother = new PoseSmoother();
    this.keypointModel = MOVENET_ID; this.detectorAvailable = true;
    this.degraded = []; this.frameCounter = 0; this.trackCounter = 0; this.generation = 0;
    this.stats = {skipped: 0, stale: 0, latencyMs: null, modelMs: {}};
    this.resetTracking('initialise');
  }

  async init() {
    if (this.ready) return this.ready;
    this.ready = (async () => {
      try { this.info = await this.backend.init(); } catch (error) {
        if (this.backend.thread !== 'worker') throw error;
        this.backend = this.fallbackBackend();
        this.degrade('worker', `Inference runs on the page thread because the background worker failed (${error.message}).`);
        this.info = await this.backend.init();
      }
      const loaded = await this.backend.load([YOLO_ID, MOVENET_ID]);
      this.applyFailures(Object.fromEntries(Object.entries(loaded).filter(([, v]) => v !== 'ready')));
      if (!this.detectorAvailable && this.keypointModel === null) throw Error('No pose model could be loaded on this device.');
      this.emitStatus();
    })();
    this.ready.catch(() => { this.ready = null; });
    return this.ready;
  }

  /** Start a new temporal context: stale in-flight results are discarded and the person is reselected. */
  resetTracking(reason) {
    this.generation++;
    this.track = {id: null, box: null, lastSeen: -Infinity, needsDetect: true};
    this.lastDetectAt = -Infinity; this.lastAccepted = this.frameCounter; this.lastTimestamp = -Infinity;
    this.smoother.reset();
    this.selection = {status: 'none', reason: ''};
    this.onEvent({type: 'reset', reason});
  }

  degrade(key, text) {
    if (!this.degraded.some(d => d.key === key)) this.degraded.push({key, text});
  }

  applyFailures(errors = {}) {
    let changed = false;
    if (errors[MOVENET_ID] && this.keypointModel === MOVENET_ID) {
      this.keypointModel = this.detectorAvailable ? YOLO_ID : null; changed = true;
      this.degrade(MOVENET_ID, this.detectorAvailable
        ? 'MoveNet is unavailable; YOLOv8n-pose provides keypoints on every inference (lower frame rate).'
        : 'MoveNet is unavailable.');
    }
    if (errors[YOLO_ID] && this.detectorAvailable) {
      this.detectorAvailable = false; changed = true;
      if (this.keypointModel === YOLO_ID) this.keypointModel = null;
      this.degrade(YOLO_ID, 'Person detection is unavailable; MoveNet runs on the full frame and cannot separate people. Keep only one person in view.');
    }
    if (changed) { this.resetTracking('model-change'); this.onEvent({type: 'model-change', keypointModel: this.keypointModel}); }
    return changed;
  }

  get minInterval() {
    const latency = (this.stats.latencyMs ?? 0) / 1000;
    return Math.max(1 / this.config.maxHz, latency * 1.1);
  }

  status() {
    const model = this.keypointModel ? MODELS[this.keypointModel].label : 'None';
    return {thread: this.backend.thread, keypointModel: this.keypointModel, keypointLabel: model,
      detector: this.detectorAvailable ? MODELS[YOLO_ID].label : null, degraded: this.degraded.map(d => d.text),
      trackId: this.track.id, selection: this.selection, latencyMs: this.stats.latencyMs,
      modelMs: Object.fromEntries(Object.entries(this.stats.modelMs).map(([k, v]) => [k, Math.round(v)])),
      skipped: this.stats.skipped, stale: this.stats.stale};
  }

  emitStatus() { this.onStatus(this.status()); }

  /**
   * Estimate the selected person's pose for the frame currently shown by `source`.
   * Returns {status, pose?, display?, reason?}. status is one of
   * ok | busy (frame skipped) | stale | no-person | no-pose | error.
   */
  async estimate(source, timestamp, {live = false} = {}) {
    if (this.busy) { this.stats.skipped++; return {status: 'busy'}; }
    if (!this.keypointModel) return {status: 'error', reason: 'No pose model is available.'};
    if (timestamp < this.lastTimestamp) this.resetTracking('seek');
    this.lastTimestamp = timestamp;
    this.busy = true;
    const frameId = ++this.frameCounter, generation = this.generation, started = clock();
    const track = this.track;
    const lost = track.box && timestamp - track.lastSeen > this.config.lostSeconds;
    if (lost) { this.resetTracking('lost'); }
    const detect = this.detectorAvailable && (this.keypointModel === YOLO_ID || !this.track.box || this.track.needsDetect ||
      timestamp - this.lastDetectAt >= this.config.reacquireSeconds);
    const request = {frameId, timestamp, generation: this.generation, detect, keypointModel: this.keypointModel,
      previousBox: this.track.id ? this.track.box : null, cropBox: this.track.box};
    let result;
    try { result = await this.backend.run(source, request); } catch (error) {
      this.busy = false;
      return {status: 'error', reason: error.message};
    }
    this.busy = false;
    const elapsed = clock() - started;
    this.stats.latencyMs = this.stats.latencyMs === null ? elapsed : this.stats.latencyMs * .8 + elapsed * .2;
    if (result.generation !== this.generation || frameId <= this.lastAccepted ||
        (live && elapsed > this.config.maxLatencySeconds * 1000)) {
      this.stats.stale++;
      return {status: 'stale'};
    }
    this.lastAccepted = frameId;
    for (const [id, ms] of Object.entries(result.timings || {})) this.stats.modelMs[id] = this.stats.modelMs[id] === undefined ? ms : this.stats.modelMs[id] * .8 + ms * .2;
    if (this.applyFailures({...result.failed, ...result.errors})) { this.emitStatus(); return {status: 'no-pose', reason: 'Switching pose model.'}; }
    if (result.detector) this.lastDetectAt = timestamp;
    if (result.selection) {
      this.selection = result.selection;
      if (result.selection.status === 'new') {
        this.track = {id: `person-${++this.trackCounter}`, box: result.box, lastSeen: timestamp, needsDetect: false};
        this.smoother.reset();
        this.onEvent({type: 'track-change', trackId: this.track.id});
      } else if (result.selection.status === 'matched') {
        this.track.lastSeen = timestamp;
      } else {
        // Keep the old box for matching; never adopt another person mid-track.
        this.track.needsDetect = true;
        this.emitStatus();
        return {status: 'no-person', reason: result.selection.reason};
      }
    }
    if (!result.keypoints) { this.track.needsDetect = true; this.emitStatus(); return {status: 'no-pose', reason: 'No pose estimate for this frame.'}; }
    if (!this.track.id) {
      // Detector unavailable: a full-frame single-person track, explicitly unverified.
      this.track = {id: `person-${++this.trackCounter}-unverified`, box: null, lastSeen: timestamp, needsDetect: false};
      this.onEvent({type: 'track-change', trackId: this.track.id});
    }
    const threshold = keypointThreshold(result.model);
    const pose = makePose({frameId, timestamp, trackId: this.track.id, model: result.model, detector: result.detector,
      width: result.frame.width, height: result.frame.height, keypoints: result.keypoints, box: result.box});
    const next = result.model === YOLO_ID ? result.box : boxFromKeypoints(result.keypoints, threshold);
    if (!next) {
      // Too few reliable joints: report the loss and verify the person with YOLO next frame.
      this.track.needsDetect = true; this.emitStatus();
      return {status: 'no-pose', reason: 'Tracking lost. Keep your whole body in view.'};
    }
    if (!result.detector && this.track.box && iou(next, this.track.box) < .3) {
      // The crop suddenly shows a differently placed body: re-verify instead of following it.
      this.track.needsDetect = true; this.emitStatus();
      return {status: 'no-pose', reason: 'Re-checking which person is being tracked.'};
    }
    this.track.box = next; this.track.lastSeen = timestamp; this.track.needsDetect = false;
    this.emitStatus();
    return {status: 'ok', pose, display: live ? this.smoother.apply(pose, threshold) : pose};
  }

  async dispose() {
    this.resetTracking('dispose');
    const backend = this.backend; this.backend = {thread: 'disposed', run: async () => { throw Error('Pose engine disposed.'); }, dispose: async () => {}};
    this.ready = null;
    await backend.dispose?.();
  }
}
