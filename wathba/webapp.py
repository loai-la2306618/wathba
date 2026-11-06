"""Patient workout frontend with real browser MediaPipe tracking."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import uuid

import cv2
import imageio_ffmpeg
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import storage, remote
from .browser_pose import process_browser_video
from .media import configure_ffmpeg, open_video
from .reporting import bundle
from .analysis import session_analysis

BASE = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()


def media_url(path):
    path = Path(path).resolve()
    return '/media/' + path.relative_to(storage.root()).as_posix()


def reference_id(exercise="squat"):
    p = storage.root()/('browser-reference.json' if exercise == 'squat' else 'browser-reference-jump.json')
    if remote.enabled():remote.ensure(p,refresh=True) if remote.exists(p) else None
    if p.exists():
        value=json.loads(p.read_text()).get('id')
        try:
            model=storage.load_reference(value)
            if model.get('pose_engine') == 'mediapipe-pose-landmarker-full' and model.get('height_normalisation') == 'static_torso_v1':
                return value
        except (OSError,ValueError,TypeError):
            pass
    return None


def prepare_library():
    folder=Path(os.getenv('WATHBA_LIBRARY_DIR',str(Path.home()/'Downloads/excercise videos')))
    out=storage.root()/'library';out.mkdir(exist_ok=True)
    for role, rel in [('therapist','therapist/WhatsApp Video 2026-11-05 at 22.44.19.mp4'),('patient','patient/WhatsApp Video 2026-11-05 at 22.44.18.mp4'),('therapist-jump','therapist/WhatsApp Video 2026-11-05 at 22.44.20.mp4'),('patient-jump','patient/WhatsApp Video 2026-11-05 at 22.44.23.mp4')]:
        source=folder/rel;target=out/(f'{role}.mp4' if role.endswith('-jump') else f'{role}-squat.mp4')
        if source.is_file() and not target.exists():shutil.copy2(source,target)
        if target.exists() and not (out/f'{role}.jpg').exists():
            cap=cv2.VideoCapture(str(target));cap.set(cv2.CAP_PROP_POS_MSEC,1500);ok,frame=cap.read();cap.release()
            if ok:cv2.imwrite(str(out/f'{role}.jpg'),frame)
    return out


def public_session(s):
    ref_source=None
    if s['plan'].get('reference_id'):
        try:ref_source=media_url(storage.load(s['plan']['reference_id'])['source_video'])
        except (OSError,ValueError):pass
    return {'id':s['id'],'exercise':s['exercise'],'side':s['plan']['side'],'view':s['plan']['view'],
            'target':s['plan']['target_repetitions'],'repetitions':s['repetitions'],'duration':s['duration'],
            'created_at':s['created_at'],'coverage':s['coverage'],'match_score':s.get('match_score',{}),'cycles':s['cycles'],
            'model':s['model'],'source':media_url(s['source_video']),'annotated':media_url(s['annotated_video']),
            'feedback':s['feedback'],'flags':[{**f,'clip':media_url(f['clip']),**{k:media_url(f[k]) for k in ('picture','reference_picture') if f.get(k)}} for f in s['flags']],
            'motion_analysis':session_analysis(s),'reference':s.get('reference_model'),'reference_source':ref_source,'report':media_url(storage.folder(s['id'])/'physio-report.html'),
            'landmarks':s.get('browser_landmarks',[]),'limitations':s.get('limitations',[])}


class ProgramRequest(BaseModel):
    target_repetitions: int = Field(ge=1,le=50)


class FeedbackRequest(BaseModel):
    text: str = Field(max_length=5000)


class TrackingRequest(BaseModel):
    asset: str
    rows: list[dict] = Field(min_length=5,max_length=2200)
    exercise: str = Field(default="squat", pattern="^(squat|jump)$")
    reference: bool = False
    consent: bool = False
    reference_id: str | None = Field(default=None,pattern='^[0-9a-f]{32}$')


def create_app():
    configure_ffmpeg()
    library=prepare_library()
    app=FastAPI(title='Wathba',docs_url=None,redoc_url=None)

    @app.get('/')
    def index():return FileResponse(BASE/'web/index.html')

    @app.get('/api/config')
    def config(exercise: str = "squat"):
        if exercise not in ("squat", "jump"):raise HTTPException(400,"Choose Squats or Jump.")
        ref=reference_id(exercise)
        m=storage.load_reference(ref) if ref else None
        teacher=Path(storage.load(ref)['source_video']) if ref else library/f'therapist-{exercise}.mp4'
        poster=teacher.parent/f'therapist-{exercise}.jpg'
        legacy_poster=teacher.parent/'therapist.jpg'
        if remote.enabled() and not remote.exists(poster) and remote.exists(legacy_poster):poster=legacy_poster
        if remote.enabled() and not poster.exists() and remote.exists(poster):remote.ensure(poster)
        if teacher.exists() and not poster.exists():
            cap=cv2.VideoCapture(str(teacher));cap.set(cv2.CAP_PROP_POS_MSEC,1500);ok,frame=cap.read();cap.release()
            if ok:cv2.imwrite(str(poster),frame)
        return {'exercise':'Squat' if exercise=='squat' else 'Jump','exerciseId':exercise,'comparisonAvailable':bool(m),'side':'Left','view':'Front','target':storage.load_plan().target_repetitions,'model':'Google MediaPipe Pose Landmarker Full',
                'referenceId':ref,'referenceModel':m,'referenceUrl':media_url(teacher) if teacher.exists() or (remote.enabled() and remote.exists(teacher)) else None,
                'sampleUrl':media_url(library/f'patient-{exercise}.mp4') if (library/f'patient-{exercise}.mp4').exists() or (remote.enabled() and remote.exists(library/f'patient-{exercise}.mp4')) else None,
                'maxUploadMb':int(os.getenv('WATHBA_MAX_UPLOAD_MB','300')),'maxRecordingSeconds':int(os.getenv('WATHBA_MAX_RECORDING_SECONDS','180')),'cameraBitrate':int(os.getenv('WATHBA_CAMERA_BITRATE','2500000')),
                'poster':media_url(poster) if poster.exists() else None}

    @app.post('/api/upload')
    async def upload(file: UploadFile = File(...)):
        upload_id=uuid.uuid4().hex
        folder=storage.root()/'uploads'/upload_id;folder.mkdir(parents=True)
        suffix=Path(file.filename or '').suffix.lower()
        if suffix not in ('.mp4','.mov','.webm','.m4v','.mkv','.avi'):suffix='.webm'
        raw=folder/('input'+suffix);size=0
        with raw.open('wb') as out:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>int(os.getenv('WATHBA_MAX_UPLOAD_MB','300'))*1024*1024:
                    raw.unlink(missing_ok=True);raise HTTPException(413,'This shared demo supports videos up to '+os.getenv('WATHBA_MAX_UPLOAD_MB','300')+' MB. Use a short recording or the provided patient video.')
                out.write(chunk)
        target=folder/'source.mp4'
        try:
            # Normalise webcam WebM metadata and phone orientation before tracking.
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-i',str(raw),'-t','181',
                            '-an','-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2','-c:v','libx264','-preset','veryfast',
                            '-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True,capture_output=True,timeout=120)
            cap,_,duration=open_video(target);cap.release()
        except (ValueError,subprocess.SubprocessError) as exc:
            target.unlink(missing_ok=True);raise HTTPException(400,'Could not read the recording. Use an MP4/MOV or a camera recording under three minutes.') from exc
        finally:raw.unlink(missing_ok=True)
        remote.persist_file(target)
        return {'asset':upload_id,'url':media_url(target),'duration':duration}

    @app.post('/api/process')
    def process(request: TrackingRequest):
        if not request.consent:raise HTTPException(400,'Confirm permission to analyse this recording.')
        if request.asset in ('therapist','patient'):
            source=library/f'{request.asset}-{request.exercise}.mp4'
            if request.reference != (request.asset=='therapist'):raise HTTPException(400,'Reference and patient sources must be separate.')
        else:
            if len(request.asset)!=32 or any(c not in '0123456789abcdef' for c in request.asset):raise HTTPException(400,'Invalid recording.')
            source=storage.root()/'uploads'/request.asset/'source.mp4'
        if remote.enabled() and not source.exists():remote.ensure(source)
        if not source.exists():raise HTTPException(404,'Recording not found. Upload it again.')
        with LOCK:
            try:
                ref=None if request.reference else request.reference_id or reference_id(request.exercise)
                if not request.reference and not ref and request.exercise=='squat':raise ValueError('Prepare the therapist reference before analysing the patient.')
                s=process_browser_video(source,request.rows,ref,request.reference,
                                        f'Therapist {request.exercise} demonstration' if request.reference else f'Patient {request.exercise} session', exercise=request.exercise)
                if request.reference:
                    target=storage.root()/('browser-reference.json' if request.exercise=='squat' else 'browser-reference-jump.json')
                    temporary=target.with_suffix('.tmp')
                    temporary.write_text(json.dumps({'id':s['id']}))
                    temporary.replace(target)
                    remote.persist_session(s['id']);remote.persist_file(target)
                    return {'id':s['id'],'model':storage.load_reference(s['id'])}
                remote.persist_session(s['id'])
                return public_session(s)
            except ValueError as exc:raise HTTPException(400,str(exc)) from exc

    @app.get('/api/session/{session_id}')
    def session(session_id:str):
        try:return public_session(storage.load(session_id))
        except (OSError,ValueError):raise HTTPException(404,'Session not found.')

    @app.post('/api/program')
    def update_program(request: ProgramRequest):
        from dataclasses import replace
        plan=replace(storage.load_plan(),target_repetitions=request.target_repetitions)
        storage.save_plan(plan)
        return {'target_repetitions':plan.target_repetitions}

    @app.post('/api/session/{session_id}/feedback')
    def update_feedback(session_id:str,request: FeedbackRequest):
        try:
            s=storage.feedback(session_id,request.text)
            remote.persist_session(session_id)
            return public_session(s)
        except (OSError,ValueError):raise HTTPException(404,'Session not found.')

    @app.get('/api/history')
    def history():
        return [{'id':s['id'],'repetitions':s['repetitions'],'score':s.get('match_score',{}).get('value'),'created':s['created_at'],'exercise':s['exercise'],'coverage':s['coverage'],'duration':s['duration']}
                for s in storage.sessions() if s.get('pose_engine')=='mediapipe-pose-landmarker-full' and s.get('height_normalisation')=='static_torso_v1' and s.get('kind')!='reference' and not s.get('internal_validation')][:100]

    @app.get('/api/demo-program')
    def demo_program():
        from .program import demo_program as build_program
        sessions=[s for s in storage.sessions() if s.get('pose_engine')=='mediapipe-pose-landmarker-full'
                  and s.get('kind')!='reference' and not s.get('internal_validation')]
        return build_program(sessions, storage.load_plan().target_repetitions)

    @app.get('/api/bundle/{session_id}')
    def export(session_id:str):
        try:s=storage.load(session_id)
        except (OSError,ValueError):raise HTTPException(404,'Session not found.')
        if remote.enabled():
            for flag in s['flags']:
                for key in ('clip','picture','reference_picture'):
                    if flag.get(key):remote.ensure(flag[key])
        path=bundle(s,storage.folder(session_id))
        if remote.enabled():
            remote.persist_file(path)
            url=remote.signed_url(path)
            if url:return RedirectResponse(url)
        return FileResponse(path,filename='wathba-review.zip')

    @app.get('/media/{path:path}')
    def shared_media(path:str):
        try:
            relative=remote.relative_path(path)
            target=(storage.root()/relative).resolve()
            target.relative_to(storage.root().resolve())
            if remote.enabled():
                url=remote.signed_url(relative)
                if url:return RedirectResponse(url)
                target=remote.ensure(relative)
            if not target.is_file():raise FileNotFoundError()
            return FileResponse(target)
        except (OSError,ValueError):raise HTTPException(404,'Media not found.')

    app.mount('/static',StaticFiles(directory=BASE/'web'),name='static')
    app.mount('/assets',StaticFiles(directory=BASE/'assets'),name='assets')
    app.mount('/vendor',StaticFiles(directory=BASE/'assets/vendor'),name='vendor')
    if not remote.enabled():app.mount('/media',StaticFiles(directory=storage.root()),name='media')
    return app
