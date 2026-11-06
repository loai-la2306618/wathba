// Module Web Worker: runs YOLOv8n-pose and MoveNet off the UI thread.
import * as ort from '/vendor/ort/ort.wasm.min.mjs';
import {PoseRuntime} from './runtime.js';

ort.env.wasm.wasmPaths = '/vendor/ort/';
// Multi-threaded WASM needs a cross-origin-isolated page; otherwise use one thread.
// Leave one core for the page (video decoding, drawing).
ort.env.wasm.numThreads = self.crossOriginIsolated ? Math.max(1, Math.min(4, (navigator.hardwareConcurrency || 2) - 1)) : 1;

let runtime = null, canvas = null, ctx = null;

function pixels(bitmap) {
  if (!canvas || canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
    canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    ctx = canvas.getContext('2d', {willReadFrequently: true});
  }
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  return {data: image.data, width: image.width, height: image.height};
}

self.onmessage = async ({data}) => {
  const {id, type} = data;
  try {
    let payload;
    if (type === 'init') {
      runtime ??= new PoseRuntime(ort, {modelSource: (model, file) => `/vendor/models/${model}/${file}`, sessionOptions: {executionProviders: ['wasm']}});
      payload = {threads: ort.env.wasm.numThreads};
    } else if (type === 'load') {
      payload = await runtime.load(data.ids);
    } else if (type === 'run') {
      const result = await runtime.run(pixels(data.bitmap), data.request);
      payload = {...result, failed: {...runtime.failed}};
    } else if (type === 'dispose') {
      await runtime?.dispose(); runtime = null; canvas = ctx = null;
      payload = {disposed: true};
    } else {
      throw Error(`Unknown pose worker message: ${type}`);
    }
    self.postMessage({id, payload});
    if (type === 'dispose') self.close();
  } catch (error) {
    data.bitmap?.close?.();
    self.postMessage({id, error: String(error?.message || error)});
  }
};
