// Test helpers: decode real video frames with the bundled ffmpeg and run the
// browser pose runtime/engine in Node through onnxruntime-node.
import {spawnSync} from 'node:child_process';
import {existsSync, readdirSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {PoseRuntime} from '../../web/pose/runtime.js';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
export const MODEL_DIR = join(ROOT, 'assets/vendor/models');
export const modelsAvailable = () => existsSync(join(MODEL_DIR, 'yolov8n-pose/model.onnx')) && existsSync(join(MODEL_DIR, 'yolov8n-pose/model_quantized.onnx')) && existsSync(join(MODEL_DIR, 'movenet-singlepose-lightning/model.onnx'));

export function ffmpegPath() {
  if (process.env.WATHBA_FFMPEG) return process.env.WATHBA_FFMPEG;
  for (const site of [join(ROOT, '.venv/Lib/site-packages'), ...(existsSync(join(ROOT, '.venv/lib')) ? readdirSync(join(ROOT, '.venv/lib')).map(p => join(ROOT, '.venv/lib', p, 'site-packages')) : [])]) {
    const folder = join(site, 'imageio_ffmpeg/binaries');
    if (existsSync(folder)) { const exe = readdirSync(folder).find(f => f.startsWith('ffmpeg')); if (exe) return join(folder, exe); }
  }
  return 'ffmpeg';
}

/** Decode `video` to RGBA frames at `fps`, long side <= maxSide (like the browser capture). */
export function decodeFrames(video, {fps = 6, maxSide = 640, width, height}) {
  const scale = Math.min(1, maxSide / Math.max(width, height));
  const w = Math.round(width * scale), h = Math.round(height * scale);
  const out = spawnSync(ffmpegPath(), ['-v', 'error', '-i', video, '-vf', `fps=${fps},scale=${w}:${h}`, '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], {maxBuffer: 1 << 30});
  if (out.status !== 0) throw Error(String(out.stderr));
  const size = w * h * 4, frames = [];
  for (let i = 0; i + size <= out.stdout.length; i += size) frames.push({data: new Uint8Array(out.stdout.buffer, out.stdout.byteOffset + i, size), width: w, height: h, time: frames.length / fps});
  return frames;
}

export function probe(video) {
  const out = spawnSync(ffmpegPath(), ['-i', video], {encoding: 'utf8'});
  const m = /, (\d{2,5})x(\d{2,5})[, ]/.exec(out.stderr);
  if (!m) throw Error('Could not read video size');
  return {width: +m[1], height: +m[2]};
}

/** Engine backend backed by onnxruntime-node; `source` is a decoded RGBA frame. */
export class NodeBackend {
  constructor(ort, original) { this.thread = 'node'; this.ort = ort; this.original = original; }
  async init() { this.runtime = new PoseRuntime(this.ort, {modelSource: (id, file) => join(MODEL_DIR, id, file)}); return {threads: 1}; }
  load(ids) { return this.runtime.load(ids); }
  async run(image, request) {
    const result = await this.runtime.run(image, request);
    return {...result, failed: {...this.runtime.failed}, frame: this.original ?? {width: image.width, height: image.height}};
  }
  async dispose() { await this.runtime.dispose(); }
}
