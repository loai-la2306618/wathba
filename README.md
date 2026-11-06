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
  - mediapipe
license: apache-2.0
---

# وثبة | Wathba

> **Current GitHub snapshot:** the earlier local UI has been restored at the owner's request. The backend retains the newer scheduling, Jump recording and evidence-report capabilities described below; some are exposed only by the separately deployed preview UI. This repository preserves the current local frontend, rather than the newer shared-preview frontend. Qwen integration and fine-tuning have not been implemented. Recordings, reference-session data, credentials and local workspaces are excluded; use therapist-reference setup to supply your own consented demonstration.

A dark-glass, mint-accented guided rehabilitation prototype for Qai × Hugging Face in Qatar. **Assigned exercise → therapist demonstration → live camera or upload → feedback and per-rep scores → skeleton/video replay → physio report.**

The patient app now uses **Google MediaPipe Pose Landmarker Full in the browser**. It tracks 33 landmarks through WebAssembly/WebGL. The Python backend compares movement with the therapist reference, extracts actual source clips and saves the report. No pretrained neural-network fine-tuning is performed.

## Run locally

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python scripts/setup_browser_assets.py
.venv/bin/python app.py
```

Open http://127.0.0.1:7860. The interface includes welcome, patient home, live exercise, completion, session summary, therapist portal, exercise library, progress and a local profile. Bottom navigation connects the screens. The welcome state is remembered on this device; `?screen=welcome` reopens it. Model/runtime assets are included in the source package; the setup command verifies/downloads their pinned versions if needed. FFmpeg encoding uses the bundled imageio binary. Installing system FFmpeg/ffprobe (`brew install ffmpeg` on macOS) is recommended for the Gradio clinician workspace.

Primary runtime: `@mediapipe/tasks-vision@0.10.32` and Google's `pose_landmarker_full/float16/1` model. JS, WASM and weights are served locally from `assets/vendor/`; setup checks npm integrity and the model SHA256. No Google/Hugging Face inference API is called. Tracking runs on the user's browser; footage and landmarks are sent to the Wathba backend for reports and evidence clips.

## The two footage roles

The team's `Downloads/excercise videos/therapist` squat clip is the **reference**, not the patient. The separate `patient` squat clip is the evaluated recording. On this laptop, the matching files are discovered and copied into the private local library. Override the library folder with `WATHBA_LIBRARY_DIR`.

On another machine, open the **Physio workspace → Set therapist reference** link (or `/?reference=1`). Upload a therapist-designated frontal squat demonstration containing at least two complete repetitions and prepare the reference. It is tracked with the same MediaPipe model used for the patient. The therapist video itself is the guide; the old mannequin is removed from the main flow. The therapist appears above the patient, with floating measured guidance between the two. Desktop preserves the compact mobile proportions in a centered app shell. The supplied dark glass/mint screen references define the interface; the original Wathba logo is retained. Generated cover/library illustrations are explicitly separate from real reference and patient footage.

The files remain local and are excluded from source packaging. Other supplied videos include landing, stepping, balance and band work. Those types are not currently claimed as validated automatic quality assessments. Current fitted assessment: **frontal squat, left leg**. Jump is also available for recording and movement measurement, with comparison withheld until its own compatible reference is prepared.

## Demo program and live feedback

Programs contains one **Demo** program with Squats and Jump, scheduled Monday, Tuesday, Thursday and Saturday in Doha time. Completion is derived from saved sessions: an exercise needs the configured repetition target in a session with at least 70% tracking coverage on the current Doha date. This is adherence progress, not recovery or form correctness. Each exercise shows its next due date and a link to its last recording. Selecting it loads that exercise on Home; selectors on Home and the workout screen switch exercises before recording.

Camera preview and recording fill the viewport, with the therapist guide in a small inset. Green means a tracked part is within the fitted reference tolerance, yellow means a difference, red a larger difference, and grey means unassessed or uncertain. The left knee and trunk comparison is approximate; the right knee is not independently assessed by the left-side profile. Live observations are debounced. Completed recordings are re-analysed and saved for review. Even an untrackable attempt is retained without a form score. A failed upload offers a local recording download.

Squats uses the separate fitted therapist reference. Jump has its own staged guide, patient footage and fixed-camera both-foot displacement measurement, sampled at 12 fps. Without a matching fitted Jump reference, it saves/counts observable movement cycles for review and withholds form scores and corrections. It does not apply the squat reference to jumps. Jumping is a demo item, not an ACL exercise prescription. References uploaded through setup must match the selected exercise and contain at least two complete repetitions.

Reports lead with flagged repetitions, body parts, exact comparison tolerances, timestamps, annotated clips and paired patient/reference stills where a reference is available. Both faster and slower tempo and both smaller and larger excursion are flagged. Colour severity describes a reference difference, not medical risk. Report ZIPs include stills and clips. Responsive layouts cover narrow phones, tablets and desktop; landscape camera controls remain usable.

## Patient flow

1. Click **Start exercise** and watch the actual therapist demonstration with its tracked skeleton.
2. Confirm permission, then select **Use camera**, **Upload video**, or the provided patient sample on this laptop.
3. Camera mode gives a live skeleton and provisional repetition counter. The top pause control pauses/resumes the recording and its timer. Click **Finish set** for the final analysis. Uploaded clips are analysed in the browser with progress shown.
4. Results show experimental reference match, duration, observed repetitions, tracking coverage and per-repetition match bars.
5. Select a bar or **Replay with skeleton** to review the original motion, toggle a dark-background skeleton view, pause, seek and jump between repetitions. The therapist replay follows the same outward/return phase as the current patient repetition; this is visual phase alignment, separate from the DTW analysis.
6. **View full report** provides real source clips, measurements, clinician feedback and HTML/ZIP downloads. Its movement-analysis section includes time to peak and return, within-set timing/excursion variation, per-feature curves and differences from the reference tolerance. Feature comparison is withheld below 70% overall tracking coverage and when an individual feature is not visible reliably. The clinician workspace can confirm/dismiss findings, add comments and return feedback.

Camera permission and a secure context are required (`localhost` works). Camera recording supports browser-supported WebM/MP4 and is normalised before final analysis so the report timestamps match the recorded video. The final count may differ from the provisional live count. Limit: 3 minutes / 300 MB.

## Motion assessment

MediaPipe's 33 landmarks are mapped to the shared body-feature representation. Original 33-point data is retained for replay. Measurements exclude unreliable landmarks and gaps; no synthetic example substitutes for a failed analysis.

Frontal squat descent uses hip-to-ankle vertical distance divided by **one robust torso scale per recording**. Using each frame's torso length can invert a squat when the torso foreshortens during forward lean. The static scale avoids that artefact. Reference waveforms are also relative to their starting position, reducing body-proportion offsets.

Complete repetitions are segmented adaptively. A fitted statistical reference stores phase-normalised curves, median/MAD variation, excursion and timing. Constrained dynamic time warping compares motion shape. Findings describe faster timing, smaller observed excursion, sustained pattern differences and lost tracking. The selected reference ID is retained per session; a later reference change cannot silently change an ongoing comparison.

The optional match score combines 80% tolerance-normalised aligned feature similarity and 20% tempo similarity. It requires a reference, complete assessable repetitions and at least 70% landmark coverage. It is a prototype similarity measure, **not clinical accuracy, recovery, strength or exercise safety**. Corrections remain tied to the treating physiotherapist's interpretation and assigned restrictions. Estimated model depth is not calibrated clinical 3D motion capture.

## Reports, review and data

The in-app Therapist Portal provides session history, progress, per-session feedback and a persisted repetition target for future recordings. `/physio` remains a separate detailed review workspace. It is a prototype role, not a separate authenticated clinician account. Sessions, uploaded footage, fitted references, 33-point tracks and reports are stored under `.wathba/` (`WATHBA_DATA_DIR` overrides it). This directory is excluded from source uploads. The source ZIP contains no therapist/patient recordings or reports.

The review ZIP contains printable HTML, JSON and playable source clips. Extract before opening the HTML; browser Print saves a PDF. Reports include reference provenance, exercise/view/side, per-repetition timing and excursion, experimental match scores, observation intervals, visibility limitations and clinician comments. No outside language model receives the footage or writes the report.

## Verification

```sh
uv pip install --python .venv/bin/python pytest
.venv/bin/python -m pytest -q
```

50 tests cover segmentation, confidence gaps, reference matching, body-proportion offsets, torso-foreshortening regression, detailed movement evidence/visibility gates, MediaPipe-to-COCO mapping, invalid/partial browser data, scores, actual generated clips and review exports.

Real browser inference was checked on the separately designated therapist and patient recordings. The therapist reference yields four complete cycles; the full patient video yields 20 observed complete cycles. Chromium and WebKit run actual MediaPipe inference and replay; live camera capture/tracking/finish was checked with the patient's footage supplied through Chromium's simulated camera. These are functional integration checks, not a held-out clinical accuracy study.

## Hosting and optional legacy tools

The private paid Hugging Face development Space is kept **paused**. The original Hugging Face Space has not been resumed. A separate password-protected team preview is deployed on Vercel, with private Hugging Face dataset storage; see `SHARING.md` for access handling and the smaller preview upload/recording limits. Local browser tracking does not consume the team's Space runtime credits. Hosting runtime billing applies when a paid Space is resumed.

The older ViTPose/RT-DETR CLI remains available for comparison, but it is not used by the new patient flow. Install `requirements-vitpose.txt` separately to run it. The linked OpenCV MediaPipe ONNX conversion is not the browser engine used here.

See `MODEL_CARD.md` and `RESEARCH_NOTES.md` for provenance and limitations. Vendor code/model attribution is under `assets/vendor/`.
