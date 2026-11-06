# Wathba browser MediaPipe delivery audit

Latest request: use the stacked therapist/patient guidance layout with navy/green logo colors and explain deeper movement analysis beyond landmark detection. Therapist and patient sources must remain separate; the designated therapist clip becomes the motion reference and visible guide.

| Requirement | Evidence |
| --- | --- |
| Logo-colored exercise overview, stacked comparison, results and replay | `web/index.html`, `style.css`; rendered desktop and 390px mobile screenshots |
| Actual Google MediaPipe in browser | Locally served `@mediapipe/tasks-vision@0.10.32`, Full task model, JS/WASM requests observed; reports identify engine and retain 33-point data |
| Real therapist reference | Teacher clip processed into four complete reference cycles; model `synthetic=false`, source role recorded |
| Separate patient evaluation | Full patient clip processed into 20 observed cycles; 18-second patient excerpt produces three complete cycles after foreshortening fix |
| Camera capture and live tracking | Chromium simulated camera uses actual patient footage; live landmarks/counter, record/finish/upload/final report exercised; final 13-second capture retains matching playback duration |
| Skeleton overlay and black skeleton-only replay | 33 detected landmarks drawn against the video or black background; pause, seek and per-repetition navigation |
| Results, per-rep bars and actual evidence clips | Experimental reference match, duration, observed reps, coverage and threshold counts; clickable bars; source clips and full report |
| Physio handoff | Actual browser test confirms marking a moment, saving a comment, feedback appearing in the patient report and downloadable ZIP; therapist-reference setup uses browser tracking too |
| Stable movement measurements | Recording-wide robust torso scale prevents torso foreshortening from inverting frontal squat motion; start-relative waveforms reduce body-proportion offsets |
| Reproducible reference provenance | Reference ID captured per comparison, compatible engine/normalisation checked, atomic reference selection update |
| Cost control | No paid inference API, local browser model; private paid HF Space remains paused and new source is not deployed |

40 Python tests cover the underlying measurement, reference, score, person-selection and report pipeline. Actual Chromium and WebKit browser inference is checked separately. The linked OpenCV MediaPipe ONNX port is useful for OpenCV integrations but is not the engine used in this browser app. ViTPose remains an optional legacy CLI, outside the primary patient flow.

Scores are prototype reference similarities, not clinical accuracy or rehabilitation outcomes. MediaPipe is pretrained and not fine-tuned here. The designated reference is not independently verified as a licensed physiotherapist or an ACL-specific prescription. Other exercise types and calibrated clinical 3D measurements are not claimed. Private recordings, reports and QA media stay outside the source ZIP.

The updated movement-evidence panel exposes measured outward/return timing, per-set coefficients of variation, phase-normalised feature curves, mean aligned differences and the fraction outside reference tolerances. The same evidence is included in printable HTML and JSON exports. It does not infer clinical weight distribution or ligament status. Replay uses piecewise outward/return phase matching to the actual therapist cycle. The interface labels live timing as provisional and landmark visibility as tracking, not performance.

Latest UI: all eight supplied dark-glass/mint screens are connected. Patient dashboard, library/search, progress filters, therapist overview/sessions/exercises/notes, program target persistence, completion and summary retain real measurements. The camera supports pause/resume. Generated photographic cover/library assets are illustrations, excluded from all reference analysis.

UI validation: Chromium checks all eight screen routes, library filtering/search, reference replay, report navigation, real camera inference and pause/resume. A changed repetition target propagates into a newly processed recording. Profile persists locally; therapist feedback persists to the patient report. Responsive checks pass at 320, 390, 768 and 1440 CSS pixels. Forty Python tests pass. Screenshots and local gallery are under artifacts and excluded from the source ZIP.
