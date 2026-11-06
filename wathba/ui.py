"""Reference fitting, patient recordings, and physiotherapist evidence review."""

import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import cv2
import gradio as gr

from . import storage
from .assessment import FEATURES
from .example import ensure_illustrative_reference
from .media import configure_ffmpeg, open_video
from .motion import Plan
from .pipeline import analyse_video, example_session, train_reference
from .presentation import (
    cycle_rows,
    flag_choices,
    flag_description,
    metrics_html,
    reference_description,
    summary_html,
    trace_data,
)
from .reporting import bundle
from .styles import CSS

EXERCISES = ["Knee bend or extension", "Squat", "Lunge", "Straight-leg raise"]
PRIMARY = [(FEATURES[n].label, n) for n in ("knee_angle", "leg_elevation", "hip_height")]


def session_options():
    return [(f"{s['label']} · {datetime.fromisoformat(s['created_at']).astimezone(ZoneInfo('Asia/Qatar')).strftime('%d %b %H:%M')} Doha · {s['id'][:6]}", s["id"])
            for s in storage.sessions() if s.get("kind") != "reference" and s.get("schema_version") == 2 and not s.get("internal_validation")]


def reference_options():
    return [("Measurements only · قياسات دون مرجع", "")] + [(f"{m.get('label',m['exercise'])} · {m['view']} · {m['training_cycles']} reps", m["reference_session_id"])
                                                            for m in storage.references() if (not m["synthetic"] or m.get("builtin")) and not m.get("internal_validation")]


def make_plan(exercise, side, view, primary, fps, reference_id="", roi=None):
    illustrated = bool(reference_id and storage.load_reference(reference_id)["synthetic"])
    return Plan(exercise=exercise, side=side, view=view, primary_feature=primary, sample_fps=int(fps),
                reference_id=reference_id or None, subject_roi=tuple(roi) if roi else None,
                allow_illustrative_reference=illustrated)


def profile_feature(exercise, view):
    return "leg_elevation" if exercise == "Straight-leg raise" else "hip_height" if exercise == "Squat" and view == "Front" else "knee_angle"


def analyse(path, label, symptoms, pain, consent, exercise, side, view, primary, reference_id, fps, roi, progress=gr.Progress()):  # noqa: B008
    if not consent:
        raise gr.Error("Confirm that the participant agreed to this recording being analysed.")
    if not path:
        raise gr.Error("Upload your exercise recording first.")
    try:
        reported_pain = None if pain in (None, "not-provided") else int(pain)
        if reported_pain is not None and not 0 <= reported_pain <= 10:
            raise ValueError("Reported pain must be between 0 and 10.")
        plan = make_plan(exercise, side, view, primary, fps, reference_id, roi)
        session = analyse_video(path, plan, label or "Exercise session", symptoms or "", reported_pain,
                                lambda value, desc: progress(value, desc=desc))
        return patient_results(session)
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    except Exception as exc:
        traceback.print_exc()
        raise gr.Error("The recording could not be analysed. Check the local app logs and retry. No example results were substituted.") from exc


def patient_results(s):
    guide = s.get("guide_video")
    if s["plan"].get("reference_id"):
        guide = storage.load(s["plan"]["reference_id"]).get("guide_video")
    return (s["id"], s["annotated_video"], metrics_html(s), summary_html(s), str(storage.folder(s["id"]) / "physio-report.html"),
            gr.Dropdown(choices=session_options(), value=s["id"]), guide)


def load_example():
    return patient_results(example_session(Plan()))


def fit_model(path, label, exercise, side, view, primary, fps, approved, pace_cue, range_cue, pattern_cue, roi, progress=gr.Progress()):  # noqa: B008
    if not path:
        raise gr.Error("Upload a reference demonstration with at least two complete repetitions.")
    try:
        session, model, model_path = train_reference(
            path, make_plan(exercise, side, view, primary, fps, roi=roi), label or "Reference demonstration", approved=approved,
            cues={"pace": pace_cue or "", "range": range_cue or "", "pattern": pattern_cue or ""},
            progress=lambda v, desc: progress(v, desc=desc))
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    except Exception as exc:
        traceback.print_exc()
        raise gr.Error("Reference fitting did not finish. Check the local logs; the video must show complete, trackable movements.") from exc
    return reference_description(model), session["guide_video"], model_path, gr.Dropdown(choices=reference_options(), value=session["id"])


def select_reference(reference_id):
    if not reference_id:
        return None, "No reference selected. The model will measure visible movement without inferring corrections.", gr.skip(), gr.skip(), gr.skip()
    model = storage.load_reference(reference_id)
    session = storage.load(reference_id)
    return session.get("guide_video"), reference_description(model), model["exercise"], model["view"], model["primary_feature"]


def preview_frame(path):
    if not path:
        return None, None, [], None, "Automatic subject selection."
    try:
        cap, _, _ = open_video(path)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise ValueError("Could not read the first video frame.")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        scale = min(1, 900 / max(frame.shape[:2]))
        frame = cv2.resize(frame, (round(frame.shape[1] * scale), round(frame.shape[0] * scale)))
        return frame, frame, [], None, "Optional: click the top-left and bottom-right corners around the participant."
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc


def select_region(raw, corners, event: gr.SelectData):
    if raw is None:
        raise gr.Error("Upload a video to choose a participant region.")
    corners = list(corners or []) + [list(event.index[:2])]
    marked = raw.copy()
    if len(corners) == 1:
        x, y = corners[0]
        cv2.drawMarker(marked, (x, y), (49, 95, 214), cv2.MARKER_CROSS, 20, 2)
        return marked, corners, None, "Now click the opposite corner of the participant's region."
    x1, x2 = sorted([corners[0][0], corners[1][0]])
    y1, y2 = sorted([corners[0][1], corners[1][1]])
    h, w = raw.shape[:2]
    roi = [x1 / w, y1 / h, x2 / w, y2 / h]
    if roi[2] - roi[0] < .05 or roi[3] - roi[1] < .05:
        raise gr.Error("Choose a larger region around the whole participant, including the leg.")
    cv2.rectangle(marked, (x1, y1), (x2, y2), (49, 95, 214), 3)
    return marked, [], roi, "Participant region selected. Keep the required joints inside this region throughout the video."


def reset_region(raw):
    return raw, [], None, "Automatic subject selection."


def subject_controls(video):
    raw, corners, roi = gr.State(None), gr.State([]), gr.State(None)
    with gr.Accordion("Choose the participant if other people are visible · تحديد المشارك", open=False):
        gr.Markdown("Automatic tracking selects one unambiguous large person. For a busy gym recording, click two opposite corners around the participant in the first frame.")
        preview = gr.Image(label="First frame · الإطار الأول", interactive=False, height=260)
        message = gr.Markdown("Upload a video to select the participant.")
        reset = gr.Button("Use automatic selection · تحديد تلقائي", size="sm")
    video.change(preview_frame, video, [preview, raw, corners, roi, message], api_name=False)
    preview.select(select_region, [raw, corners], [preview, corners, roi, message], api_name=False)
    reset.click(reset_region, raw, [preview, corners, roi, message], api_name=False)
    return roi


def refresh_patient(session_id):
    if not session_id:
        raise gr.Error("Analyse a recording or open the illustrative example first.")
    return summary_html(storage.load(session_id))


def refresh_sessions():
    options = session_options()
    return gr.Dropdown(choices=options, value=options[0][1] if options else None)


def load_session(session_id):
    if not session_id:
        return "", None, "", None, gr.Dropdown(choices=[], value=None), None, flag_description(None), "Pending", "", "", None, []
    s = storage.load(session_id)
    first = s["flags"][0] if s["flags"] else None
    feature = FEATURES[s.get("primary_feature", "knee_angle")]
    return (metrics_html(s), s["annotated_video"], summary_html(s),
            gr.LinePlot(value=trace_data(s), x="Seconds", y="Measured value", color="Series", y_title=f"{feature.label} ({feature.unit})", height=230),
            gr.Dropdown(choices=flag_choices(s), value=first["id"] if first else None), first["clip"] if first else None,
            flag_description(first), first["status"] if first else "Pending", first["comment"] if first else "", s["feedback"],
            str(storage.folder(session_id) / "physio-report.html"), cycle_rows(s))


def select_flag(session_id, flag_id):
    if not session_id or not flag_id:
        return None, flag_description(None), "Pending", ""
    s = storage.load(session_id)
    flag = next((f for f in s["flags"] if f["id"] == flag_id), None)
    return (flag["clip"], flag_description(flag), flag["status"], flag["comment"]) if flag else (None, flag_description(None), "Pending", "")


def save_review(session_id, flag_id, status, comment):
    if not session_id or not flag_id:
        raise gr.Error("Choose a session and a review moment first.")
    s = storage.review(session_id, flag_id, status, comment or "")
    gr.Info("Review saved. / تم حفظ المراجعة.")
    return summary_html(s), gr.Dropdown(choices=flag_choices(s), value=flag_id), str(storage.folder(session_id) / "physio-report.html")


def send_feedback(session_id, text):
    if not session_id:
        raise gr.Error("Choose a session first.")
    s = storage.feedback(session_id, text or "")
    gr.Info("Feedback saved. / تم حفظ الملاحظات.")
    return summary_html(s), str(storage.folder(session_id) / "physio-report.html")


def export_bundle(session_id):
    if not session_id:
        raise gr.Error("Choose a session first.")
    return bundle(storage.load(session_id), storage.folder(session_id))


def build_app():
    from dataclasses import replace
    from pathlib import Path
    import json

    from .experience import assigned_exercise, feedback as patient_feedback, header, progress as steps, recent_sessions, report_heading, stage_heading

    configure_ffmpeg()
    default_model, default_reference = ensure_illustrative_reference("Front")
    assignment_path = storage.root() / "assignment.json"
    if not assignment_path.exists():
        assigned = replace(storage.load_plan(), reference_id=default_model["reference_session_id"], allow_illustrative_reference=True)
        assignment_path.write_text(json.dumps(assigned.dict()))

    def assignment():
        return Plan(**json.loads(assignment_path.read_text()))

    plan = assignment()
    cover_path = storage.root() / "exercise-cover.jpg"
    cap = cv2.VideoCapture(default_reference["guide_video"])
    cap.set(cv2.CAP_PROP_POS_MSEC, 700)
    ok, frame = cap.read()
    cap.release()
    if ok:
        cv2.imwrite(str(cover_path), frame)

    def pages(name):
        return [gr.update(visible=name == item) for item in ("home", "exercise", "feedback", "report", "physio")]

    def assigned_guide():
        p = assignment()
        if p.reference_id:
            return storage.load(p.reference_id).get("guide_video")
        return ensure_illustrative_reference(p.view)[1]["guide_video"] if p.exercise == "Squat" else None

    def result_outputs(s):
        first = s["flags"][0] if s["flags"] else None
        return (s["id"], patient_feedback(s), s["annotated_video"], report_heading(s), summary_html(s),
                gr.LinePlot(value=trace_data(s), x="Seconds", y="Measured value", color="Series", height=230),
                gr.Dropdown(choices=flag_choices(s), value=first["id"] if first else None),
                first["clip"] if first else None, flag_description(first),
                str(storage.folder(s["id"]) / "physio-report.html"),
                gr.Dropdown(choices=session_options(), value=s["id"]),
                gr.Dropdown(choices=recent_sessions(), value=s["id"]), *pages("feedback"))

    def run_patient(mode, uploaded, filmed, notes, pain, consented, roi, progress=gr.Progress()):
        path = filmed if mode == "Use camera" else uploaded
        if not path:
            raise gr.Error("Record your set or upload a video first.")
        if not consented:
            raise gr.Error("Confirm permission to analyse the recording.")
        try:
            p = replace(assignment(), subject_roi=tuple(roi) if roi and mode == "Upload video" else None)
            s = analyse_video(path, p, f"{p.exercise} session", notes or "", None if pain == "not-provided" else int(pain),
                              lambda v, desc: progress(v, desc=desc))
            return result_outputs(s)
        except ValueError as exc:
            raise gr.Error(str(exc)) from exc
        except Exception as exc:
            traceback.print_exc()
            raise gr.Error("Analysis did not finish. Your recording has not been replaced with demo results. Try a shorter, clear recording.") from exc

    def demo():
        return result_outputs(example_session(assignment()))

    def reopen(session_id):
        if not session_id:
            raise gr.Error("Choose a previous session first.")
        return result_outputs(storage.load(session_id))

    def source_mode(mode):
        return gr.update(visible=mode == "Upload video"), gr.update(visible=mode == "Use camera")

    def assignment_save(exercise, side, view, feature, reference_id, target):
        p = make_plan(exercise, side, view, feature, 6, reference_id)
        if exercise != "Squat" and not reference_id:
            raise gr.Error("Fit a matching demonstration before assigning this exercise.")
        if reference_id:
            m = storage.load_reference(reference_id)
            if m["exercise"] != exercise or m["side"] != side or m["view"] != view or m["primary_feature"] != feature:
                raise gr.Error("Choose a reference matching the exercise, leg and camera view.")
        p = replace(p, target_repetitions=int(target))
        assignment_path.write_text(json.dumps(p.dict()))
        guide_path = assigned_guide()
        updated_cover = storage.root() / f"{p.reference_id or p.view}-cover.jpg"
        cap = cv2.VideoCapture(guide_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, 700)
        ok, frame = cap.read()
        cap.release()
        if ok:
            cv2.imwrite(str(updated_cover), frame)
        return ("Exercise assigned. The patient's next recording will use this plan.", assigned_exercise(p, updated_cover if ok else cover_path),
                guide_path, stage_heading(p), gr.update(visible=exercise == "Squat" and bool(clip_config.get("path"))))

    theme = gr.themes.Base(primary_hue="emerald", secondary_hue="slate", neutral_hue="slate", radius_size="lg").set(
        body_background_fill="#F7FAF8", body_background_fill_dark="#F7FAF8", body_text_color="#142D4E", body_text_color_dark="#142D4E",
        block_background_fill="#FFFFFF", block_background_fill_dark="#FFFFFF", button_primary_background_fill="#142D4E", button_primary_text_color="#FFFFFF")
    with gr.Blocks(title="Wathba | وثبة", theme=theme, css=CSS, analytics_enabled=False) as app:
        patient_id = gr.State("")
        with gr.Row(elem_classes="topbar"):
            with gr.Column(scale=3, min_width=180):
                gr.HTML(header())
            home_nav = gr.Button("My exercises", size="sm", scale=0, elem_classes="nav-button")
            physio_nav = gr.Button("Physio workspace", size="sm", scale=0, elem_classes="nav-button")
        with gr.Column(visible=True, elem_classes="page") as home_page:
            gr.HTML('<div class="intro home-intro"><h1>Your exercises.</h1><p>One session at a time. Let’s get moving.</p></div>')
            exercise_card = gr.HTML(assigned_exercise(plan, cover_path))
            with gr.Row(elem_classes="home-actions"):
                start = gr.Button("Start exercise", variant="primary", size="lg", scale=2)
                try_demo = gr.Button("Try a demo session", size="lg", scale=1)
            gr.HTML('<p class="home-note">Watch the movement. Record your set. Get feedback.</p>')
            with gr.Accordion("Previous sessions", open=False):
                past = gr.Dropdown(choices=recent_sessions(), label="Your saved sessions")
                open_past = gr.Button("Open session")
        with gr.Column(visible=False, elem_classes="page") as exercise_page:
            gr.HTML(steps(0))
            exercise_title = gr.HTML(stage_heading(plan))
            with gr.Row(elem_classes="recording-stage"):
                with gr.Column(scale=1, min_width=280):
                    gr.HTML('<div class="stage-label"><b>1</b> Watch the movement</div>')
                    guide = gr.Video(assigned_guide(), label="Exercise demonstration", show_label=False, interactive=False, height=370, loop=True, autoplay=True)
                    gr.HTML('<p class="quiet guide-note">Illustrated movement guide. Use the range assigned by your physiotherapist.</p>')
                with gr.Column(scale=1, min_width=280):
                    gr.HTML('<div class="stage-label"><b>2</b> Record your set</div>')
                    mode = gr.Radio(["Upload video", "Use camera"], value="Upload video", label="Recording method", show_label=False, elem_classes="source-toggle")
                    upload = gr.Video(label="Upload your exercise video", sources=["upload"], include_audio=False, height=290)
                    camera = gr.Video(label="Record with your camera", sources=["webcam"], include_audio=False, height=290, visible=False)
                    demo_clip_path = storage.root() / "demo-recording.json"
                    clip_config = json.loads(demo_clip_path.read_text()) if demo_clip_path.exists() else {}
                    provided_clip = gr.Button("Use your provided squat video", visible=plan.exercise == "Squat" and bool(clip_config.get("path")), size="sm")
            gr.HTML('<p class="record-hint">Keep your whole body in view and the camera steady. Up to 3 minutes / 300 MB.</p>')
            with gr.Accordion("Add a note (optional)", open=False):
                notes = gr.Textbox(label="How did the exercise feel?", lines=2)
                pain = gr.Dropdown(choices=[("Not provided", "not-provided")] + [(str(i), str(i)) for i in range(11)], value="not-provided", label="Pain you felt, 0–10")
            with gr.Accordion("Choose who to track (only if needed)", open=False):
                gr.Markdown("If other people are visible, click two corners around yourself in this first frame. This applies to uploaded footage.")
                raw, corners, roi = gr.State(None), gr.State([]), gr.State(None)
                preview = gr.Image(label="Choose the participant", interactive=False, height=260)
                region_message = gr.Markdown("Upload a video to select the participant.")
                reset = gr.Button("Track automatically", size="sm")
            consent = gr.Checkbox(label="I have permission to analyse this recording.", value=False)
            analyse_btn = gr.Button("Finish & get feedback", variant="primary", size="lg")
        with gr.Column(visible=False, elem_classes="page feedback-page") as feedback_page:
            gr.HTML(steps(1))
            result = gr.HTML()
            details_btn = gr.Button("View detailed report", variant="primary", size="lg")
            again = gr.Button("Record another set", size="lg")
        with gr.Column(visible=False, elem_classes="page") as report_page:
            gr.HTML(steps(2))
            detailed_title = gr.HTML()
            back_results = gr.Button("Back to feedback", size="sm")
            with gr.Row():
                with gr.Column(scale=1):
                    patient_video = gr.Video(label="Your movement with tracking", interactive=False, height=390)
                    patient_trace = gr.LinePlot(x="Seconds", y="Measured value", color="Series", height=230, label="Your movement and demonstration")
                with gr.Column(scale=1):
                    patient_flags = gr.Dropdown(label="Moments to review", choices=[])
                    patient_clip = gr.Video(label="Original footage", interactive=False, height=260)
                    patient_flag_details = gr.HTML()
            patient_summary = gr.HTML()
            with gr.Row():
                patient_download = gr.File(label="Download report", interactive=False)
                export_btn = gr.Button("Download report & clips", variant="primary")
                patient_bundle = gr.File(label="Report package", interactive=False)
            refresh_feedback = gr.Button("Refresh physiotherapist feedback")
        with gr.Column(visible=False, elem_classes="page physio-page") as physio_page:
            gr.HTML('<div class="intro"><h1>Physio workspace</h1><p>Review the evidence, send feedback, and assign the next exercise.</p></div>')
            with gr.Tabs():
                with gr.Tab("Review sessions"):
                    with gr.Row():
                        session_select = gr.Dropdown(label="Session", choices=session_options(), scale=4)
                        reload_btn = gr.Button("Refresh", scale=1)
                    clinician_metrics = gr.HTML()
                    with gr.Row():
                        with gr.Column(scale=3):
                            clinician_video = gr.Video(label="Full tracked recording", interactive=False, height=330)
                            timeline = gr.LinePlot(label="Movement and reference", x="Seconds", y="Measured value", color="Series", height=230)
                        with gr.Column(scale=2):
                            flags_select = gr.Dropdown(label="Moment to review", choices=[])
                            flag_video = gr.Video(label="Source footage clip", interactive=False, height=230)
                            flag_details = gr.HTML(flag_description(None))
                            review_status = gr.Radio(["Pending", "Confirmed", "Dismissed"], value="Pending", label="Your assessment")
                            review_comment = gr.Textbox(label="Comment on this moment", lines=2)
                            review_btn = gr.Button("Save review", variant="primary")
                    repetitions = gr.Dataframe(headers=["Rep", "Video interval", "Cycle seconds", "Movement excursion", "Observations"], label="Repetition detail", interactive=False)
                    clinician_report = gr.HTML()
                    feedback_text = gr.Textbox(label="Feedback for the participant", lines=3)
                    feedback_btn = gr.Button("Save feedback", variant="primary")
                    clinician_download = gr.File(label="Readable report", interactive=False)
                    bundle_btn = gr.Button("Export report and clips")
                    bundle_file = gr.File(label="Review package", interactive=False)
                with gr.Tab("Exercise & reference"):
                    gr.Markdown("### Assigned exercise\nThese settings are kept out of the patient's recording flow.")
                    with gr.Row():
                        assign_exercise = gr.Dropdown(EXERCISES, value=plan.exercise, allow_custom_value=True, label="Exercise")
                        assign_side = gr.Radio(["Left", "Right"], value=plan.side, label="Tracked leg")
                        assign_target = gr.Number(value=plan.target_repetitions, minimum=1, maximum=50, precision=0, label="Target repetitions")
                    with gr.Row():
                        assign_view = gr.Radio(["Side", "Front"], value=plan.view, label="Camera view")
                        assign_primary = gr.Dropdown(PRIMARY, value=plan.primary_feature, label="Movement measure")
                        assign_reference = gr.Dropdown(reference_options(), value=plan.reference_id or "", label="Demonstration reference")
                    assign_btn = gr.Button("Assign exercise", variant="primary")
                    assigned_status = gr.Markdown()
                    with gr.Accordion("Fit a reference from a recording", open=False):
                        gr.Markdown("Use a separate reviewed demonstration with at least two complete repetitions. Fitting a comparison model does not retrain the pose network.")
                        ref_upload = gr.Video(label="Reference demonstration", sources=["upload"], include_audio=False, height=300)
                        ref_roi = subject_controls(ref_upload)
                        ref_label = gr.Textbox(label="Reference name")
                        with gr.Row():
                            ref_exercise = gr.Dropdown(EXERCISES, value=plan.exercise, allow_custom_value=True, label="Reference exercise")
                            ref_side = gr.Radio(["Left", "Right"], value=plan.side, label="Demonstrated leg")
                            ref_view = gr.Radio(["Side", "Front"], value="Side", label="Reference camera view")
                        ref_primary = gr.Dropdown(PRIMARY, value="knee_angle", label="Primary movement measure")
                        ref_fps = gr.Slider(3, 12, value=6, step=1, label="Reference samples per second")
                        ref_approved = gr.Checkbox(label="I confirmed this demonstration and the cues with the physiotherapist", value=False)
                        pace_cue = gr.Textbox(label="Physio cue: faster repetition")
                        range_cue = gr.Textbox(label="Physio cue: smaller movement range")
                        pattern_cue = gr.Textbox(label="Physio cue: movement-pattern difference")
                        fit_btn = gr.Button("Fit reference", variant="primary")
                        ref_summary = gr.HTML()
                        ref_guide = gr.Video(label="Generated movement guide", interactive=False, loop=True)
                        model_download = gr.File(label="Fitted motion model", interactive=False)
        gr.HTML('<div class="footer"><span>Wathba · كل حركة بداية</span><span>Prototype · observations for physiotherapist review</span></div>')
        page_outputs = [home_page, exercise_page, feedback_page, report_page, physio_page]
        outputs = [patient_id, result, patient_video, detailed_title, patient_summary, patient_trace, patient_flags, patient_clip,
                   patient_flag_details, patient_download, session_select, past, *page_outputs]
        home_nav.click(lambda: pages("home"), outputs=page_outputs, api_name=False)
        physio_nav.click(lambda: pages("physio"), outputs=page_outputs, api_name=False)
        def begin_clean():
            return (*pages("exercise"), gr.update(value=None, visible=True), gr.update(value=None, visible=False), False, "Upload video", "", "not-provided", None, None, [], "Upload a video to select the participant.")
        begin_outputs = [*page_outputs, upload, camera, consent, mode, notes, pain, roi, raw, corners, region_message]
        start.click(begin_clean, outputs=begin_outputs, api_name=False)
        again.click(begin_clean, outputs=begin_outputs, api_name=False)
        mode.input(source_mode, mode, [upload, camera], api_name=False)
        provided_clip.click(lambda: (gr.update(value=clip_config.get("path"), visible=True), "Upload video", gr.update(visible=False)),
                            outputs=[upload, mode, camera], api_name=False)
        upload.change(preview_frame, upload, [preview, raw, corners, roi, region_message], api_name=False)
        preview.select(select_region, [raw, corners], [preview, corners, roi, region_message], api_name=False)
        reset.click(reset_region, raw, [preview, corners, roi, region_message], api_name=False)
        analyse_btn.click(run_patient, [mode, upload, camera, notes, pain, consent, roi], outputs,
                          api_name="finish_session", concurrency_id="pose", concurrency_limit=1)
        try_demo.click(demo, outputs=outputs, api_name="illustrative_example", concurrency_limit=1)
        open_past.click(reopen, past, outputs, api_name="open_session")
        details_btn.click(lambda: pages("report"), outputs=page_outputs, api_name=False)
        back_results.click(lambda: pages("feedback"), outputs=page_outputs, api_name=False)
        def patient_moment(session_id, flag_id):
            clip, details, _, _ = select_flag(session_id, flag_id)
            return clip, details
        patient_flags.input(patient_moment, [patient_id, patient_flags], [patient_clip, patient_flag_details], api_name=False)
        export_btn.click(export_bundle, patient_id, patient_bundle, api_name=False)
        refresh_feedback.click(refresh_patient, patient_id, patient_summary, api_name=False)
        reload_btn.click(refresh_sessions, outputs=session_select, api_name=False)
        session_outputs = [clinician_metrics, clinician_video, clinician_report, timeline, flags_select, flag_video, flag_details, review_status, review_comment, feedback_text, clinician_download, repetitions]
        session_select.change(load_session, session_select, session_outputs, api_name="load_session")
        flags_select.input(select_flag, [session_select, flags_select], [flag_video, flag_details, review_status, review_comment], api_name="select_moment")
        review_btn.click(save_review, [session_select, flags_select, review_status, review_comment], [clinician_report, flags_select, clinician_download], api_name="save_review")
        feedback_btn.click(send_feedback, [session_select, feedback_text], [clinician_report, clinician_download], api_name="save_feedback")
        bundle_btn.click(export_bundle, session_select, bundle_file, api_name="export_review")
        fit_btn.click(fit_model, [ref_upload, ref_label, ref_exercise, ref_side, ref_view, ref_primary, ref_fps, ref_approved, pace_cue, range_cue, pattern_cue, ref_roi],
                      [ref_summary, ref_guide, model_download, assign_reference], api_name="fit_reference", concurrency_id="pose", concurrency_limit=1)
        assign_btn.click(assignment_save, [assign_exercise, assign_side, assign_view, assign_primary, assign_reference, assign_target],
                         [assigned_status, exercise_card, guide, exercise_title, provided_clip], api_name="assign_exercise")
        assign_exercise.input(profile_feature, [assign_exercise, assign_view], assign_primary, api_name=False)
        assign_view.input(profile_feature, [assign_exercise, assign_view], assign_primary, api_name=False)
        ref_exercise.input(profile_feature, [ref_exercise, ref_view], ref_primary, api_name=False)
        ref_view.input(profile_feature, [ref_exercise, ref_view], ref_primary, api_name=False)
    return app
