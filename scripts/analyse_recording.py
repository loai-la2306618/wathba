"""Analyse or fit a reference locally without starting paid Hugging Face compute."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wathba import storage
from wathba.media import configure_ffmpeg
from wathba.motion import Plan
from wathba.pipeline import analyse_video, train_reference
from wathba.reporting import bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--exercise", required=True)
    parser.add_argument("--side", choices=["Left", "Right"], required=True)
    parser.add_argument("--view", choices=["Side", "Front"], default="Side")
    parser.add_argument("--feature", choices=["knee_angle", "leg_elevation", "hip_height"], default="knee_angle")
    parser.add_argument("--fps", type=int, default=6)
    parser.add_argument("--label", default="Exercise session")
    parser.add_argument("--notes", default="")
    parser.add_argument("--roi", type=float, nargs=4, metavar=("X1", "Y1", "X2", "Y2"))
    parser.add_argument("--reference-id", help="Previously fitted reference session ID")
    parser.add_argument("--allow-illustrative-reference", action="store_true", help="Explicitly compare with a labelled synthetic guide; not a clinical standard")
    parser.add_argument("--fit-reference", action="store_true", help="Fit this video as a reference instead of assessing it")
    parser.add_argument("--reference-approved", action="store_true", help="The user confirms physio review of the reference and cues")
    parser.add_argument("--pace-cue", default="")
    parser.add_argument("--range-cue", default="")
    parser.add_argument("--pattern-cue", default="")
    args = parser.parse_args()
    configure_ffmpeg()
    plan = Plan(exercise=args.exercise, side=args.side, view=args.view, primary_feature=args.feature,
                sample_fps=args.fps, reference_id=args.reference_id,
                subject_roi=tuple(args.roi) if args.roi else None, allow_illustrative_reference=args.allow_illustrative_reference)
    if args.fit_reference:
        session, model, model_path = train_reference(
            args.video, plan, args.label, approved=args.reference_approved,
            cues={"pace": args.pace_cue, "range": args.range_cue, "pattern": args.pattern_cue})
        result = {"reference_id": session["id"], "fitted_model": model_path,
                  "reference_cycles": model["training_cycles"], "animated_guide": session["guide_video"]}
    else:
        session = analyse_video(args.video, plan, args.label, args.notes, None)
        result = {"session_id": session["id"], "repetitions": session["repetitions"], "tracking_coverage": session["coverage"],
                  "assessment": session["assessment_status"], "observations": [f["detail"] for f in session["flags"]]}
    result.update(report=str(storage.folder(session["id"]) / "physio-report.html"),
                  annotated_video=session["annotated_video"], review_bundle=bundle(session, storage.folder(session["id"])))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
