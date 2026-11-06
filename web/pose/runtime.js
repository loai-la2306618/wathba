// Inference core shared by the Web Worker, the main-thread fallback and Node
// tests. `ort` is injected (onnxruntime-web in browsers, onnxruntime-node in tests).
import {MODELS} from './schema.js';
import {decodeMovenet, decodeYolo, fullFrameCrop, movenetCrop, movenetPreprocess, selectPerson, yoloPreprocess} from './adapters.js';

export const YOLO_ID = 'yolov8n-pose';
export const MOVENET_ID = 'movenet-singlepose-lightning';
const now = () => (globalThis.performance ?? Date).now();
const message = e => String(e?.message || e).slice(0, 300);

export class PoseRuntime {
  /** modelSource(id, file) -> URL or file path of one of the model's ONNX files. Sessions load lazily on first use. */
  constructor(ort, {modelSource, sessionOptions = {}} = {}) {
    this.ort = ort; this.modelSource = modelSource; this.sessionOptions = sessionOptions;
    this.sessions = new Map(); this.failed = {};
  }

  async session(id, purpose = 'keypoints') {
    const file = MODELS[id].files?.[purpose] ?? 'model.onnx', key = `${id}/${file}`;
    if (this.failed[id]) throw Error(this.failed[id]);
    if (!this.sessions.has(key)) {
      const pending = this.ort.InferenceSession.create(this.modelSource(id, file), {graphOptimizationLevel: 'all', ...this.sessionOptions})
        .catch(e => { this.failed[id] = `Could not load ${MODELS[id].label}: ${message(e)}`; this.sessions.delete(key); throw Error(this.failed[id]); });
      this.sessions.set(key, pending);
    }
    return this.sessions.get(key);
  }

  /** Load (in parallel) and warm up: the first run of a session is much slower than later ones. */
  async load(ids, {warmup = true} = {}) {
    const status = {};
    // Download/compile in parallel; run warm-ups one at a time (one WebAssembly instance).
    // YOLO is preloaded as the (quantized) detector; its full-precision keypoint weights load only when needed.
    const loaded = await Promise.allSettled(ids.map(id => this.session(id, id === YOLO_ID ? 'detection' : 'keypoints')));
    for (const [i, id] of ids.entries()) {
      if (loaded[i].status === 'rejected') { status[id] = message(loaded[i].reason); continue; }
      try {
        if (warmup) {
          const blank = {data: new Uint8Array(64 * 64 * 4), width: 64, height: 64};
          await (id === YOLO_ID ? this.yolo(blank) : this.movenet(blank, {x: 0, y: 0, w: 64, h: 64}));
        }
        status[id] = 'ready';
      } catch (e) { status[id] = message(e); }
    }
    return status;
  }

  async yolo(image, purpose = 'detection') {
    const session = await this.session(YOLO_ID, purpose), input = yoloPreprocess(image);
    const out = await session.run({[MODELS[YOLO_ID].input.name || session.inputNames[0]]: new this.ort.Tensor('float32', input.data, input.dims)});
    const tensor = out[MODELS[YOLO_ID].output.name] ?? out[session.outputNames[0]];
    return decodeYolo(tensor.data, tensor.dims);
  }

  async movenet(image, rect) {
    const session = await this.session(MOVENET_ID), input = movenetPreprocess(image, rect);
    const out = await session.run({[MODELS[MOVENET_ID].input.name || session.inputNames[0]]: new this.ort.Tensor('int32', input.data, input.dims)});
    const tensor = out[MODELS[MOVENET_ID].output.name] ?? out[session.outputNames[0]];
    return decodeMovenet(tensor.data, rect, image);
  }

  /**
   * One pipeline step for one captured frame.
   * request: {frameId, timestamp, detect, previousBox, cropBox, keypointModel}
   * - detect: run YOLO, then select the tracked person (no switching to bystanders)
   * - keypointModel: which model's keypoints this recording uses; outputs of
   *   different models are never mixed or averaged within one result.
   */
  async run(image, request) {
    const {frameId, timestamp, detect, previousBox = null, keypointModel = MOVENET_ID} = request;
    const result = {frameId, timestamp, generation: request.generation, frame: {width: image.width, height: image.height},
      model: null, keypoints: null, box: request.cropBox ?? null, detector: null, selection: null, timings: {}, errors: {}};
    let yoloKeypoints = null;
    if (detect && !this.failed[YOLO_ID]) {
      const started = now();
      try {
        const detections = await this.yolo(image, keypointModel === YOLO_ID ? 'keypoints' : 'detection');
        const choice = selectPerson(detections, previousBox);
        result.selection = {status: choice.status, reason: choice.reason, people: detections.length};
        result.detector = YOLO_ID;
        if (!choice.detection) { result.box = null; return result; }
        result.box = choice.detection.box; yoloKeypoints = choice.detection.keypoints;
      } catch (e) { result.errors[YOLO_ID] = message(e); }
      result.timings[YOLO_ID] = now() - started;
    }
    if (keypointModel === MOVENET_ID && !this.failed[MOVENET_ID]) {
      const started = now();
      try {
        const rect = result.box ? movenetCrop(result.box, image) : fullFrameCrop(image);
        result.keypoints = await this.movenet(image, rect);
        result.model = MOVENET_ID;
        result.crop = [rect.x / image.width, rect.y / image.height, (rect.x + rect.w) / image.width, (rect.y + rect.h) / image.height];
      } catch (e) { result.errors[MOVENET_ID] = message(e); }
      result.timings[MOVENET_ID] = now() - started;
      return result;
    }
    if (keypointModel === YOLO_ID && yoloKeypoints) { result.keypoints = yoloKeypoints; result.model = YOLO_ID; }
    return result;
  }

  async dispose() {
    const sessions = [...this.sessions.values()];
    this.sessions.clear();
    for (const pending of sessions) {
      try { await (await pending).release?.(); } catch { /* already released or never loaded */ }
    }
  }
}
