# Browser pose runtime and models

Installed by `scripts/setup_browser_assets.py`. Every file is pinned by SHA256 in `manifest.json`. The files are served locally from `/vendor/`; no inference API is called.

| Files | Source | Licence |
| --- | --- | --- |
| `ort/` | `onnxruntime-web@1.30.0` (npm, integrity-checked): `ort.wasm.min.mjs`, `ort-wasm-simd-threaded.{mjs,wasm}` | MIT (`ort/LICENSE`) |
| `models/yolov8n-pose/` (`model_quantized.onnx` for detection, `model.onnx` for keypoints) | [JustViping/team-qh-005-wathba-yolov8n-pose](https://huggingface.co/JustViping/team-qh-005-wathba-yolov8n-pose) @ `0f109c03e892`, fine-tuned from [Xenova/yolov8n-pose](https://huggingface.co/Xenova/yolov8n-pose) on MPII Human Pose photos (research use) @ `da4224085e2f6ce4c9ff9b670e28765194619db2`, ONNX export of Ultralytics YOLOv8n-pose | **AGPL-3.0** |
| `models/movenet-singlepose-lightning/` | [Xenova/movenet-singlepose-lightning](https://huggingface.co/Xenova/movenet-singlepose-lightning) @ `ed0f314bb7356fd1dbf1e4f52c2d40791bf6534f`, ONNX export of Google MoveNet SinglePose Lightning | Apache-2.0 |


**AGPL-3.0 notice.** The YOLOv8n-pose weights are AGPL-3.0, as published on Hugging Face. Serving them to users' browsers distributes them, and offering the app over a network brings the AGPL network clause into play. Anyone deploying Wathba must either comply with AGPL-3.0 for the combined work (including offering the corresponding source) or obtain an Ultralytics enterprise licence. Alternatively, they can remove YOLOv8n-pose: the engine then runs MoveNet on the full frame, in an explicitly degraded single-person mode.

Wathba does not retrain these networks. All three models output 17 COCO keypoints in 2D image coordinates with model-specific scores, and no depth.
