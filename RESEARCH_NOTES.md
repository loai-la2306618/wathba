# Research references and implementation decisions

## RehabAI

[Repository](https://github.com/nancyhamdan/RehabAI). Reviewed its README, frontend exercise component, backend prediction wrapper and repository tree. It uses MoveNet Thunder for pose extraction, DTW for feedback and a separately trained transformer-based score targeting KiMORE lower-back exercises. That trained score is not directly applicable to ACL squats. No licence file was found in the inspected tree. No repository code, weights or video assets were copied into Wathba.

The relevant product structure is assigned exercise → demonstration → recording → feedback → report. Wathba implements its own version with the supplied branding and a separate physio workspace.

## On-device exercise study

[Heo et al., Healthcare 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC12940220/). Describes pretrained MediaPipe/BlazePose tracking plus custom exercise analysis and feedback. The study involved apparently healthy young adults and a single-arm intervention; it does not establish ACL-specific performance. Its dataset is not publicly released, and the article supplies no downloadable implementation/model. Wathba has not inherited the paper's reported accuracy or clinical validation.

The useful architectural distinction is pretrained pose extraction followed by exercise-specific assessment and clinician review. Wathba's current CPU upload/record workflow retains ViTPose/RT-DETR through Hugging Face. Continuous on-device live coaching is a future capability, not a current claim.

## What actual team footage changed

The short squat video is frontal/oblique. A side-view knee projection produced inconsistent excursion estimates across visually similar repetitions. The assigned prototype now uses frontal pelvic descent normalised by torso length and by each repetition's initial position, with a matching original frontal animation. Comparison feedback reports timing/pattern differences rather than diagnosing a movement error. The four-repetition clip passes the full model-to-physio-report workflow; other exercise types are not claimed as validated assessments.

## Browser MediaPipe switch requested by the user

The new patient flow uses Google's Pose Landmarker Full through `@mediapipe/tasks-vision`, running in the browser. The user-linked [OpenCV HF model](https://huggingface.co/opencv/pose_estimation_mediapipe) is an ONNX conversion intended for OpenCV; it is not interchangeable with the browser Tasks package. [Google's web guide](https://developers.google.com/mediapipe/solutions/vision/pose_landmarker/web_js) describes the Tasks API used here. Runtime and model files are locally served and version/hash pinned.

The supplied folders clarified source roles: the short four-repetition clip belongs to `therapist`, while the longer squat set belongs to `patient`. Main-flow reference fitting and evaluation now use those separate sources. No synthetic mannequin reference is used. A stable torso scale was necessary because normalising each frame by a foreshortening torso distorted frontal squat signals. Regression tests cover that physical failure mode. Switching the backbone alone would not fix that measurement issue.
