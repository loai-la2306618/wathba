# Wathba motion comparison model

Pose estimation uses three models. YOLOv8n-pose is fine-tuned here; the other two are pretrained:

- **YOLOv8n-pose** (`JustViping/team-qh-005-wathba-yolov8n-pose` (fine-tuned on MPII exercise photos from `Xenova/yolov8n-pose`), ONNX, AGPL-3.0) runs in the browser. It detects people, selects one (the largest, only when unambiguous; never a non-overlapping bystander once tracking) and reacquires about once a second.
- **MoveNet SinglePose Lightning** (`Xenova/movenet-singlepose-lightning`, ONNX, Apache-2.0) runs in the browser. It returns keypoints for the selected person's square crop, which are mapped back to the original frame.

Both return 17 COCO keypoints in 2D with model-specific scores, and no depth. The 2D image-plane coordinates are converted into the shared `wathba.pose/1` named-joint schema. Weights and runtime are pinned by revision and SHA256 (`assets/vendor/manifest.json`).

The therapist-designated video is the recorded comparison reference and demonstration. A separate patient recording or camera clip is evaluated. No synthetic mannequin/reference is used in the main flow. The current profile is a frontal squat with left leg tracking; Jump is available as a separate demonstration/recording profile with both-foot displacement tracking. It is not scored against the squat reference; without a separately fitted Jump reference, form comparison is withheld. Neither profile is clinically validated.

Named COCO-17 joints feed the motion feature code directly. Reliability uses each model's own threshold (YOLO 0.5, MoveNet 0.3; provisional, uncalibrated), and one recording uses one keypoint model throughout. References are compared only with recordings from the same keypoint model; otherwise comparison is withheld. Frontal pelvic descent is normalised with a static robust torso scale (75th percentile of reliable projected torso lengths per recording). This prevents instantaneous torso foreshortening from creating or inverting squat cycles. Hip-height waveforms subtract their start value to reduce body-proportion offsets. Camera view and exercise must match; these remain approximate 2D camera measurements. Depth, world coordinates, heel/toe landmarks and 3D joint angles are unavailable and are reported as such. Earlier MediaPipe sessions remain viewable with their stored results.

The statistical reference model fits 61-point phase curves, median/MAD variation, excursion and cycle duration. Constrained dynamic time warping compares movement patterns. Threshold exceedances are observations, not diagnoses. The selected reference ID and source role are preserved in report provenance.

Reference match averages 80% aligned movement similarity and 20% tempo similarity across assessable repetitions. It is withheld without a reference, complete cycles or 70% coverage. The score formula is not clinically calibrated. Landmark coverage indicates usable primary-feature observations, not pose accuracy or exercise correctness. No healing, force, strength, load symmetry or return-to-sport claim is made.

Verification: 35 automated tests; actual MediaPipe inference on the designated therapist clip (four complete cycles) and separate full patient squat recording (20 observed complete cycles). Chromium and WebKit upload/replay flows were checked. Chromium live camera integration was checked using actual patient footage as a simulated camera stream. None of these establish clinical sensitivity/specificity or generalisation across ACL patients.

Data and reports remain in the shared private prototype workspace. Camera recordings are normalised and re-analysed after finishing for accurate media timestamps; the provisional live counter can differ from the final count. Physio feedback is stored with the session. No external language model produces reports. Paid HF hosting remains paused until explicitly resumed.

Demo schedule: four sessions weekly (Mon/Tue/Thu/Sat, Doha); completion measures recorded participation, not recovery. Reports include per-finding parts, tolerances, annotated evidence clips and paired images. Live colour feedback is reference-relative, with unassessed parts grey. Untrackable recordings are saved without form scores. No external exercise-recognition dataset was added or used.
