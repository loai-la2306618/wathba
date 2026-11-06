// Development check: run the browser pose engine (same code, onnxruntime-node)
// over a video at the browser's 6 fps analysis rate and write wathba.pose/1 rows.
//   node scripts/track_video.mjs <video> <rows.json> [--keypoint-model yolov8n-pose]
// The rows are what the browser would POST to /api/process.
import {writeFileSync} from 'node:fs';
import * as ort from 'onnxruntime-node';
import {decodeFrames, NodeBackend, probe} from '../tests/js/helpers.mjs';
import {PoseEngine} from '../web/pose/engine.js';

const [video, output, flag, forced] = process.argv.slice(2);
if (!video || !output) { console.error('usage: node scripts/track_video.mjs <video> <rows.json> [--keypoint-model id]'); process.exit(2); }
const dims = probe(video);
const frames = decodeFrames(video, {fps: 6, ...dims});
const engine = new PoseEngine({backend: new NodeBackend(ort, dims)});
await engine.init();
if (flag === '--keypoint-model') engine.keypointModel = forced;
engine.resetTracking('new recording');
const rows = [], started = Date.now();
for (const frame of frames) {
  const r = await engine.estimate(frame, frame.time);
  const p = r.status === 'ok' ? r.pose : null;
  rows.push(p ? {schema: p.schema, time: +frame.time.toFixed(5), frameId: p.frameId, trackId: p.trackId, model: p.model, detector: p.detector, keypoints: p.keypoints, box: p.box}
    : {time: +frame.time.toFixed(5), keypoints: null, model: null, trackId: null, reason: r.reason || r.status});
}
writeFileSync(output, JSON.stringify(rows));
console.log(JSON.stringify({frames: rows.length, detected: rows.filter(r => r.keypoints).length, ms_per_frame: +((Date.now() - started) / rows.length).toFixed(1), status: engine.status()}));
await engine.dispose();
