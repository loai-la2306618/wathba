---
title: Wathba · وثبة
emoji: 🦿
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
python_version: '3.12'
tags:
  - qai-hf-hackathon-2026
  - physiotherapy
  - pose-estimation
  - yolov8-pose
  - movenet
  - vitpose
license: apache-2.0
---

# وثبة | Wathba

> **Current GitHub snapshot:** the earlier local UI has been restored at the owner's request. The backend retains the newer scheduling, Jump recording and evidence-report capabilities described below; some are exposed only by the separately deployed preview UI. This repository preserves the current local frontend, rather than the newer shared-preview frontend. Qwen integration and fine-tuning have not been implemented. Recordings, reference-session data, credentials and local workspaces are excluded; use therapist-reference setup to supply your own consented demonstration.

A dark-glass, mint-accented guided rehabilitation prototype for Qai × Hugging Face in Qatar. **Assigned exercise → therapist demonstration → live camera or upload → feedback and per-rep scores → skeleton/video replay → physio report.**

The patient app tracks pose in the browser with **ONNX Runtime Web**, using three pretrained models with separate roles:

| Model | Where | Role |
| --- | --- | --- |
| `Xenova/yolov8n-pose` (AGPL-3.0) | Browser, Web Worker | Person detection, first pose, and reacquisition every ~1 s; multi-person selection |
| `Xenova/movenet-singlepose-lightning` (Apache-2.0) | Browser, Web Worker | Continuous keypoints on the selected person's crop, mapped back to frame coordinates |
| `usyd-community/vitpose-base-simple` (Apache-2.0) | Wathba backend, on request | Selected-frame check (repetition start/peak) on the tracker's person boxes |

All three output 17 COCO keypoints in 2D with model-specific scores. They do not output MediaPipe's 33 landmarks, depth or visibility. Results use a shared named-joint schema (`web/pose/models.json`, `wathba.pose/1`). The Python backend compares movement with the therapist reference, extracts actual source clips and saves the report. No pretrained neural-network fine-tuning is performed.

## Run locally

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python scripts/setup_browser_assets.py
.venv/bin/python app.py
```

Open http://127.0.0.1:7860. The interface includes welcome, patient home, live exercise, completion, session summary, therapist portal, exercise library, progress and a local profile. Bottom navigation connects the screens. The welcome state is remembered on this device; `?screen=welcome` reopens it. Model/runtime assets are included in the source package; the setup command verifies/downloads their pinned versions if needed. FFmpeg encoding uses the bundled imageio binary. Installing system FFmpeg/ffprobe (`brew install ffmpeg` on macOS) is recommended for the Gradio clinician workspace.

Browser runtime: `onnxruntime-web@1.30.0` (WebAssembly) plus the YOLOv8n-pose and MoveNet ONNX weights at pinned Hugging Face revisions. They are served locally from `assets/vendor/`, and setup checks the npm integrity and every file's SHA256. No inference API is called. Tracking runs in a Web Worker in the user's browser (on the page thread if workers are unavailable). Footage and keypoints are sent to the Wathba backend for reports and evidence clips, as before.

**Licence:** YOLOv8n-pose is AGPL-3.0. See `assets/vendor/NOTICE.md` before deploying.

### Optional ViTPose check service

ViTPose-B ships only PyTorch weights (~344 MB, 86M parameters) and needs a person box per frame, so it runs in the existing FastAPI backend rather than the browser:

```sh
uv pip install --python .venv/bin/python -r requirements-vitpose.txt   # torch (CPU), transformers 4.57.1
.venv/bin/python app.py
```

The report page shows **Run ViTPose check** when these packages are installed. The check needs an explicit consent tick, and runs on the recording already uploaded to the Wathba server; no third-party service is used. `POST /api/session/{id}/vitpose-check` with `{"consent": true}` re-analyses repetition start/peak frames, at most 24, using the stored person boxes. The first run downloads the weights from Hugging Face at the pinned revision. Set `WATHBA_OFFLINE=1` to use only the local cache, or `WATHBA_VITPOSE=0` to disable the check. Without the packages, the endpoint returns 503 with the reason, and the report says the check is unavailable. Results are stored separately as `model_checks.vitpose`, as per-frame differences between the browser model and ViTPose. They never change the session score.

Performance: the server sends cross-origin isolation headers (COOP/COEP), so ONNX Runtime uses up to 4 WebAssembly threads. Set `WATHBA_CROSS_ORIGIN_ISOLATION=0` to turn this off; it is off by default in remote-storage mode. Models preload and warm up in the background on the home screen, and the pinned runtime and model files are cached by the browser for a week. Person detection uses YOLOv8n-pose's 8-bit quantized weights (3.7 MB instead of 13.5 MB; boxes matched full precision with IoU ≥ 0.97 on the test clip). The full-precision weights load only if YOLO has to supply measurement keypoints. On the 16.5 s test clip in Edge, analysis takes about 8 s (previously 14 s), and live inference takes about 55 ms per frame (previously 126 ms).

Tuning: `WATHBA_POSE_MAX_HZ` (default 15; capped at 8 on devices with ≤4 cores or ≤4 GB) and `WATHBA_POSE_REACQUIRE_SECONDS` (default 1).

## The two footage roles

The team's `Downloads/excercise videos/therapist` squat clip is the **reference**, not the patient. The separate `patient` squat clip is the evaluated recording. On this laptop, the matching files are discovered and copied into the private local library. Override the library folder with `WATHBA_LIBRARY_DIR`.

On another machine, open the **Physio workspace → Set therapist reference** link (or `/?reference=1`). Upload a therapist-designated frontal squat demonstration containing at least two complete repetitions and prepare the reference. It is tracked with the same browser pose models used for the patient. A reference is only compared with recordings tracked by the same keypoint model. A reference fitted by the previous MediaPipe engine is re-tracked automatically from its own video the next time a session starts. The therapist video itself is the guide; the old mannequin is removed from the main flow. The therapist appears above the patient, with floating measured guidance between the two. Desktop preserves the compact mobile proportions in a centered app shell. The supplied dark glass/mint screen references define the interface; the original Wathba logo is retained. Generated cover/library illustrations are explicitly separate from real reference and patient footage.

The files remain local and are excluded from source packaging. Other supplied videos include landing, stepping, balance and band work. Those types are not currently claimed as validated automatic quality assessments. Current fitted assessment: **frontal squat, left leg**. Jump is also available for recording and movement measurement, with comparison withheld until its own compatible reference is prepared.

## Demo program and live feedback

Programs contains one **Demo** program with Squats and Jump, scheduled Monday, Tuesday, Thursday and Saturday in Doha time. Completion is derived from saved sessions: an exercise needs the configured repetition target in a session with at least 70% tracking coverage on the current Doha date. This is adherence progress, not recovery or form correctness. Each exercise shows its next due date and a link to its last recording. Selecting it loads that exercise on Home; selectors on Home and the workout screen switch exercises before recording.

Camera preview and recording fill the viewport, with the therapist guide in a small inset. Green means a tracked part is within the fitted reference tolerance, yellow means a difference, red a larger difference, and grey means unassessed or uncertain. The left knee and trunk comparison is approximate; the right knee is not independently assessed by the left-side profile. Live observations are debounced. Completed recordings are re-analysed and saved for review. Even an untrackable attempt is retained without a form score. A failed upload offers a local recording download.

Squats uses the separate fitted therapist reference. Jump has its own staged guide, patient footage and fixed-camera both-foot displacement measurement, sampled at 12 fps. Without a matching fitted Jump reference, it saves/counts observable movement cycles for review and withholds form scores and corrections. It does not apply the squat reference to jumps. Jumping is a demo item, not an ACL exercise prescription. References uploaded through setup must match the selected exercise and contain at least two complete repetitions.

Reports lead with flagged repetitions, body parts, exact comparison tolerances, timestamps, annotated clips and paired patient/reference stills where a reference is available. Both faster and slower tempo and both smaller and larger excursion are flagged. Colour severity describes a reference difference, not medical risk. Report ZIPs include stills and clips. Responsive layouts cover narrow phones, tablets and desktop; landscape camera controls remain usable.

## AI coach (Qwen3, local)

The report has an **AI coach** card with three optional features. Each one needs a consent tick, and all of them run on the Wathba server with local Hugging Face models, so session data is not sent to any other service:

- **Session summary** in the interface language, written by `Qwen/Qwen3-4B-Instruct-2507` (4-bit NF4 on GPUs under 12 GB) from the measured results and the patient's post-exercise answers.
- **Questions about the session.** Clinical decisions (healing, more load, return to sport) are referred to the physiotherapist.
- **Vision model review** (experimental, under Technical details). `Qwen/Qwen3-VL-4B-Instruct` describes the start and bottom frames of the first repetitions. It never changes the score.

Every reply is checked by `wathba/coach.py` before it is shown:
- every number must come from the session (simple differences of two measured values are allowed);
- no diagnosis, healing or return-to-sport claims (negated or conditional sentences are allowed);
- a referral to the physiotherapist when the patient reported pain ≥5/10, instability or swelling;
- no contradiction of the patient's answers, and the correct repetition count;
- the requested language, with no third-script characters and no leaked data field names;
- a short length.

A failing summary is regenerated once and withheld if it still fails; a failing answer is replaced by a fixed referral. When the answers need attention and the model omits the referral, the app adds a fixed safety sentence instead of relying on the model. Arabic answers use Arabic instructions and Arabic fact labels.

```sh
pip install -r requirements-qwen.txt      # CUDA 12.x PyTorch, transformers 4.57.1, accelerate, bitsandbytes
python app.py                             # models download on first use (about 3 GB for each 4B model in 4-bit)
```

Environment variables:
- `WATHBA_QWEN_TEXT_MODEL`: one of `qwen3-0.6b`, `qwen3-1.7b`, `qwen3-4b`.
- `WATHBA_QWEN_VISION_MODEL`: `qwen3-vl-2b` or `qwen3-vl-4b`.
- `WATHBA_QWEN=0`: disables the AI coach.
- `WATHBA_OFFLINE=1`: uses only the local model cache.

Only one model is kept in GPU memory at a time. A hosted provider (Hugging Face Inference API) can be added behind `wathba/llm.py` later. It is not enabled, because it would send patient data off the machine.

**Benchmark:** `python scripts/benchmark_qwen.py --video frontal-squat.mp4` compares Qwen3-0.6B/1.7B/4B and Qwen3-VL-2B/4B on this machine. Results are in `benchmarks/qwen3/RESULTS.md`. `--rescore` re-applies updated checks to saved outputs without generating them again.

## Patient flow

The live target counter includes complete, assessable repetitions with a rounded reference-match score of at least 60%, capped at the assigned target. This progress count is separate from strictly correct repetitions. The summary reports all observed repetitions and how many fully met the reference tolerances. It requires a stable start, visible shoulders/knees/ankles, a complete return, and reference-relative range, timing and alignment checks. An isolated missed frame is tolerated; sustained tracking loss interrupts the current attempt. Final analysis stores observed cycles separately from `accepted_repetitions`; missing comparison features cannot count as a match. Upload-analysis percentage is shown separately from the repetition counter, including on failure. Sound alerts play two short tones for sustained differences or a rejected repetition during live recording and uploaded-video analysis, with a six-second cooldown, a mute button and a Test sound button. Sound requires browser audio support and is unlocked by an explicit button press. These are approximate reference comparisons, not clinical correctness labels.

1. Click **Start exercise** and watch the actual therapist demonstration with its tracked skeleton.
2. Confirm permission, then select **Use camera**, **Upload video**, or the provided patient sample on this laptop.
3. Camera mode gives a live skeleton and provisional repetition counter. The top pause control pauses/resumes the recording and its timer. Click **Finish set** for the final analysis. Uploaded clips are analysed in the browser with progress shown.
4. Results show experimental reference match, duration, observed repetitions, tracking coverage and per-repetition match bars.
5. Select a bar or **Replay with skeleton** to review the original motion, toggle a dark-background skeleton view, pause, seek and jump between repetitions. The therapist replay follows the same outward/return phase as the current patient repetition; this is visual phase alignment, separate from the DTW analysis.
6. **View full report** provides real source clips, measurements, clinician feedback and HTML/ZIP downloads. Its movement-analysis section includes time to peak and return, within-set timing/excursion variation, per-feature curves and differences from the reference tolerance. Feature comparison is withheld below 70% overall tracking coverage and when an individual feature is not visible reliably. The clinician workspace can confirm/dismiss findings, add comments and return feedback.

Camera permission and a secure context are required (`localhost` works). Camera recording supports browser-supported WebM/MP4 and is normalised before final analysis so the report timestamps match the recorded video. The final count may differ from the provisional live count. Limit: 3 minutes / 300 MB.

The post-workout evaluation opens as a separate page after **Finish Session**. Use **Continue exercises** to add more completed recordings before evaluating. Pain, effort, instability, swelling and notes describe the whole workout; one evaluation is linked to every included patient recording with an explicit workout scope. It is no longer embedded in individual exercise results. Pending workout recording IDs survive navigation and refresh in the current tab until answers are saved.

## Motion assessment

Keypoints are addressed by anatomical name (`left_hip`, …), normalised to the original, unmirrored frame. The live camera preview is mirrored for display only; inference always uses unmirrored frames, so `left_knee` is the patient's left knee. A joint counts as reliable only above its own model's threshold: YOLOv8n-pose 0.5, MoveNet 0.3, ViTPose 0.3. These are provisional defaults taken from each model's reference demos and have not been calibrated. Scores are never treated as MediaPipe visibility or compared across models. One recording uses one keypoint model throughout. If MoveNet fails, the whole analysis restarts with YOLOv8n-pose keypoints, and the active model is shown under the status pill. Samples from a different tracked person are excluded. Measurements exclude unreliable joints and gaps; no synthetic example substitutes for a failed analysis. Sessions recorded with the previous MediaPipe engine stay listed and replayable (their 17 COCO-equivalent landmarks only), with their original stored results.

**No longer available** because the COCO-17 models lack the data:
- Landmark depth (`z`) and world coordinates. MediaPipe's estimates were stored but never used in scoring; they are now `null`.
- Heel and toe (foot-index) landmarks: skeleton feet, heel-lift/toe-contact and foot-progression measures. Jump lift continues to use the ankles, as it did before.
- Hand and face detail landmarks (pinky/index/thumb, mouth, inner/outer eyes).
- Any 3D knee-flexion angle. Knee and hip angles are 2D image-plane estimates and change with camera position.

The report lists these under **Pose models** (`unavailable_measurements`).

Frontal squat descent uses hip-to-ankle vertical distance divided by **one robust torso scale per recording**. Using each frame's torso length can invert a squat when the torso foreshortens during forward lean. The static scale avoids that artefact. Reference waveforms are also relative to their starting position, reducing body-proportion offsets.

Complete repetitions are segmented adaptively. A fitted statistical reference stores phase-normalised curves, median/MAD variation, excursion and timing. Constrained dynamic time warping compares motion shape. Findings describe faster timing, smaller observed excursion, sustained pattern differences and lost tracking. The selected reference ID is retained per session; a later reference change cannot silently change an ongoing comparison.

The optional match score combines 80% tolerance-normalised aligned feature similarity and 20% tempo similarity. It requires a reference, complete assessable repetitions and at least 70% landmark coverage. It is a prototype similarity measure, **not clinical accuracy, recovery, strength or exercise safety**. Corrections remain tied to the treating physiotherapist's interpretation and assigned restrictions. No depth is estimated; all measurements are 2D image-plane values, not clinical 3D motion capture.

## Reports, review and data

The in-app Therapist Portal provides session history, progress, per-session feedback and a persisted repetition target for future recordings. `/physio` remains a separate detailed review workspace. It is a prototype role, not a separate authenticated clinician account. Sessions, uploaded footage, fitted references, named-keypoint tracks and reports are stored under `.wathba/` (`WATHBA_DATA_DIR` overrides it). This directory is excluded from source uploads. The source ZIP contains no therapist/patient recordings or reports.

The review ZIP contains printable HTML, JSON and playable source clips. Extract before opening the HTML; browser Print saves a PDF. Reports include reference provenance, exercise/view/side, per-repetition timing and excursion, experimental match scores, observation intervals, visibility limitations and clinician comments. No outside language model receives the footage or writes the report.

## Verification

```sh
uv pip install --python .venv/bin/python pytest
.venv/bin/python -m pytest -q          # Python: schema, features, ViTPose service/endpoint, pipeline
npm install && npm test                # Node (dev only): adapters, transforms, engine, real ONNX models
WATHBA_TEST_VIDEO=/path/to/frontal-squat.mp4 npm test   # also runs the real-model multi-person/occlusion tests
node scripts/track_video.mjs video.mp4 rows.json        # browser engine on a video -> wathba.pose/1 rows
```

The Node tests import the same `web/pose/*.js` modules as the browser and run them with `onnxruntime-node`. They cover crop/resize/padding transforms, YOLO/MoveNet decoding, anatomical left/right under mirroring, person selection, ambiguity and bystanders, low-confidence and occluded joints, stale and late results, frame skipping, model fallback, worker fallback and model disposal. The Python tests cover per-model thresholds, missing joints and depth, mixed-model and other-person rows, reference/model compatibility, legacy-record replay, and the ViTPose box conversion, endpoint consent, 503 behaviour and saved results. A real ViTPose test runs when `WATHBA_TEST_VIDEO` is set and the optional packages are installed.

Migration check (2026-11-06) on one 16.5 s frontal barbell-squat clip, 464×832. Frames were inspected by eye: standing until 9 s, then 3 complete squats bottoming at ~10.2, 12.5 and 14.9 s. Both MoveNet and YOLO-only tracking gave 3 repetitions at 100% coverage. A headless Edge run of the real app gave the same count for sample analysis and for live camera capture (simulated camera from the same clip), with no console errors. ViTPose differed from MoveNet by a median 3.5° (2D knee angle) and ~0.2 torso lengths (per-frame hip height) on 6 frames. That is inter-model disagreement, not accuracy. This is one clip of one person, not a validation study; reference annotations on representative patient recordings are still needed.

## Hosting and optional legacy tools

The private paid Hugging Face development Space is kept **paused**. The original Hugging Face Space has not been resumed. A separate password-protected team preview is deployed on Vercel, with private Hugging Face dataset storage; see `SHARING.md` for access handling and the smaller preview upload/recording limits. Local browser tracking does not consume the team's Space runtime credits. Hosting runtime billing applies when a paid Space is resumed.

The older ViTPose-plus/RT-DETR CLI (`scripts/analyse_recording.py`) remains available for offline comparison; it is separate from the patient flow and the ViTPose check above.

See `MODEL_CARD.md` and `RESEARCH_NOTES.md` for provenance and limitations. Vendor code/model attribution is under `assets/vendor/`.
