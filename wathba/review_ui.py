"""Separate clinician review workspace for MediaPipe sessions."""
import gradio as gr
from . import storage
from .ui import load_session,select_flag,save_review,send_feedback,export_bundle


def choices():
    return [(f"{s['label']} · {s['created_at'][11:16]} UTC · {s['id'][:6]}",s['id']) for s in storage.sessions()
            if s.get('pose_engine')=='mediapipe-pose-landmarker-full' and s.get('kind')!='reference' and not s.get('internal_validation')]


def build_review_app():
    theme=gr.themes.Base(primary_hue='green',neutral_hue='slate').set(body_background_fill='#080808',body_background_fill_dark='#080808',body_text_color='#f5f7f5',body_text_color_dark='#f5f7f5',block_background_fill='#151515',block_background_fill_dark='#151515')
    with gr.Blocks(title='Wathba · Physio review',theme=theme,analytics_enabled=False,css='.gradio-container{max-width:1100px!important}.session-summary,.review-note{padding:20px;line-height:1.8}.measurements{display:flex;gap:30px;padding:15px}.measurements strong{display:block;font-size:28px}.measurements span{font-size:12px}.source-badge,.cue{color:#66dbc0}.measurement-note{color:#a0a6a1}.session-summary h3{margin:20px 0 10px}.observation-list{padding-left:20px}') as demo:
        gr.Markdown('# Wathba · Physio review\nReview actual patient recordings, source clips and the therapist-reference comparison. [Back to patient app](/) · [Set therapist reference](/?reference=1)')
        with gr.Row():
            selected=gr.Dropdown(choices=choices(),label='Session',scale=4)
            refresh=gr.Button('Refresh sessions',scale=1)
        metrics=gr.HTML()
        with gr.Row():
            with gr.Column(scale=3):
                video=gr.Video(label='Patient recording with tracking',interactive=False)
                trace=gr.LinePlot(label='Movement and therapist reference',x='Seconds',y='Measured value',color='Series')
            with gr.Column(scale=2):
                flags=gr.Dropdown(choices=[],label='Moment to review')
                clip=gr.Video(label='Original patient footage',interactive=False)
                details=gr.HTML()
                status=gr.Radio(['Pending','Confirmed','Dismissed'],value='Pending',label='Your assessment')
                comment=gr.Textbox(label='Comment on this moment',lines=2)
                review=gr.Button('Save review',variant='primary')
        reps=gr.Dataframe(headers=['Rep','Interval','Duration','Excursion','Observations'],label='Repetition detail',interactive=False)
        summary=gr.HTML()
        feedback=gr.Textbox(label='Feedback for the patient',lines=3)
        save=gr.Button('Save feedback',variant='primary')
        report=gr.File(label='Printable report',interactive=False)
        export=gr.Button('Export report and clips')
        download=gr.File(label='Review package',interactive=False)
        outputs=[metrics,video,summary,trace,flags,clip,details,status,comment,feedback,report,reps]
        def refresh_review():
            options=choices()
            session_id=options[0][1] if options else None
            return gr.Dropdown(choices=options,value=session_id), *load_session(session_id)
        refresh.click(refresh_review,outputs=[selected,*outputs],api_name='refresh',queue=False)
        selected.change(load_session,selected,outputs,api_name='load_session',queue=False)
        flags.input(select_flag,[selected,flags],[clip,details,status,comment],api_name='select_moment',queue=False)
        review.click(save_review,[selected,flags,status,comment],[summary,flags,report],api_name='save_review',queue=False)
        save.click(send_feedback,[selected,feedback],[summary,report],api_name='save_feedback',queue=False)
        export.click(export_bundle,selected,download,api_name='export_review',queue=False)
    return demo
