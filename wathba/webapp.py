"""Patient workout frontend with browser pose tracking (YOLOv8n-pose + MoveNet) and a server ViTPose check."""

import gzip
import json
import mimetypes
import os
from pathlib import Path
import shutil
import subprocess
import threading
import uuid

import cv2
import imageio_ffmpeg
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import BaseModel, Field

from . import storage, remote
from . import ai as ai_coach, llm, vitpose_service
from .browser_pose import HEIGHT_NORMALISATION, process_browser_video
from .pose_schema import LEGACY_MEDIAPIPE_ENGINE, MODELS, PIPELINE, replay_rows, unavailable_measurements
from .media import configure_ffmpeg, open_video
from .reporting import bundle
from .analysis import session_analysis
from .assessment import cycle_matches_reference
from .scoring import counted_repetitions

BASE = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()
# Windows can map .mjs/.wasm to the wrong type from the registry; module workers
# and WebAssembly streaming compilation require these exact types.
mimetypes.add_type('text/javascript', '.mjs')
mimetypes.add_type('text/javascript', '.js')
mimetypes.add_type('application/wasm', '.wasm')
mimetypes.add_type('application/json', '.json')
mimetypes.add_type('application/manifest+json', '.webmanifest')
SESSION_ENGINES = (PIPELINE, LEGACY_MEDIAPIPE_ENGINE)


def env_number(name, default, low, high):
    try:
        value = float(os.getenv(name, default))
    except ValueError:
        return default
    return min(high, max(low, value))


def media_url(path):
    path = Path(path).resolve()
    return '/media/' + path.relative_to(storage.root()).as_posix()


def _reference_pointer(exercise):
    p = storage.root()/('browser-reference.json' if exercise == 'squat' else 'browser-reference-jump.json')
    if remote.enabled():remote.ensure(p,refresh=True) if remote.exists(p) else None
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8')).get('id')
    except (OSError, ValueError):
        return None


def reference_id(exercise="squat"):
    """The active reference, only if it was fitted with the current pose pipeline."""
    value = _reference_pointer(exercise)
    if value:
        try:
            model=storage.load_reference(value)
            if model.get('pose_engine') == PIPELINE and model.get('height_normalisation') == HEIGHT_NORMALISATION:
                return value
        except (OSError,ValueError,TypeError):
            pass
    return None


def legacy_reference_source(exercise="squat"):
    """Source video of a reference fitted by the removed MediaPipe engine, to re-fit it."""
    value = _reference_pointer(exercise)
    if not value or reference_id(exercise):
        return None
    try:
        source = Path(storage.load(value)['source_video'])
    except (OSError, ValueError, KeyError):
        return None
    return source if source.exists() or (remote.enabled() and remote.exists(source)) else None


def prepare_library():
    bundled=Path(__file__).resolve().parents[1]/'demo-media'  # Clips shipped with the deployed demo.
    folder=Path(os.getenv('WATHBA_LIBRARY_DIR') or (bundled if bundled.is_dir() else Path.home()/'Downloads/excercise videos'))
    out=storage.root()/'library';out.mkdir(exist_ok=True)
    for role, rel in [('therapist','therapist/WhatsApp Video 2026-11-05 at 22.44.19.mp4'),('patient','patient/WhatsApp Video 2026-11-05 at 22.44.18.mp4'),('therapist-jump','therapist/WhatsApp Video 2026-11-05 at 22.44.20.mp4'),('patient-jump','patient/WhatsApp Video 2026-11-05 at 22.44.23.mp4')]:
        source=folder/rel;target=out/(f'{role}.mp4' if role.endswith('-jump') else f'{role}-squat.mp4')
        if source.is_file() and not target.exists():shutil.copy2(source,target)
        if target.exists() and not (out/f'{role}.jpg').exists():
            cap=cv2.VideoCapture(str(target));cap.set(cv2.CAP_PROP_POS_MSEC,1500);ok,frame=cap.read();cap.release()
            if ok:cv2.imwrite(str(out/f'{role}.jpg'),frame)
    return out


def seed_reference(library):
    """Hosted disks are wiped on restart, so rebuild the squat reference from its saved tracking."""
    rows=Path(__file__).resolve().parents[1]/'demo-media/therapist-squat.rows.json'
    source=library/'therapist-squat.mp4'
    if reference_id('squat') or not rows.is_file() or not source.is_file():
        return
    try:
        s=process_browser_video(source,json.loads(rows.read_text(encoding='utf-8')),None,True,'Therapist squat demonstration',exercise='squat')
        target=storage.root()/'browser-reference.json'
        temporary=target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'id':s['id']}), encoding='utf-8')
        temporary.replace(target)
    except Exception as exc:  # The app must still start; a reference can be prepared from the browser.
        print(f'Could not rebuild the therapist reference: {exc}',flush=True)


def session_response(request, session, **headers):
    """Session JSON is mostly repetitive landmarks, so compress it for phones."""
    response=JSONResponse(public_session(session),headers=headers)
    if len(response.body)>1024 and 'gzip' in request.headers.get('accept-encoding',''):
        response.body=gzip.compress(response.body,1)
        response.headers.update({'content-encoding':'gzip','content-length':str(len(response.body)),'vary':'Accept-Encoding'})
    return response


def known_reference(value):
    """False for an id from before a restart, which a tab left open can still send."""
    try:
        return bool(value and storage.load_reference(value))
    except (OSError,ValueError,TypeError):
        return False


def reference_locked():
    return os.getenv('WATHBA_LOCK_REFERENCE')=='1'


def public_session(s):
    ref_source=None
    cycles=s['cycles']
    # Earlier saved reports predate the explicit accepted count. Evaluate their
    # existing cycles against their original reference rather than returning 0.
    if 'accepted_repetitions' not in s and s.get('reference_model'):
        try:
            reference=storage.load_reference(s['plan']['reference_id'])
            cycles=[{**c,'accepted':cycle_matches_reference(c,s['samples'],reference,s['coverage'],s['plan']['primary_feature']),
                     'comparison_assessable':cycle_matches_reference({**c,'findings':[]},s['samples'],reference,s['coverage'],s['plan']['primary_feature'])} for c in cycles]
        except (OSError,ValueError,KeyError):pass
    if s['plan'].get('reference_id'):
        try:ref_source=media_url(storage.load(s['plan']['reference_id'])['source_video'])
        except (OSError,ValueError):pass
    return {'id':s['id'],'exercise':s['exercise'],'side':s['plan']['side'],'view':s['plan']['view'],
            'target':s['plan']['target_repetitions'],'repetitions':s['repetitions'],'duration':s['duration'],
            'accepted_repetitions':s.get('accepted_repetitions',sum(c.get('accepted') is True for c in cycles)),
            'counted_repetitions':s.get('counted_repetitions',counted_repetitions(cycles,s.get('match_score',{}))),
            'created_at':s['created_at'],'coverage':s['coverage'],'match_score':s.get('match_score',{}),'cycles':cycles,
            'model':s['model'],'source':media_url(s['source_video']),'annotated':media_url(s['annotated_video']),
            'feedback':s['feedback'],'flags':[{**f,'clip':media_url(f['clip']),**{k:media_url(f[k]) for k in ('picture','reference_picture') if f.get(k)}} for f in s['flags']],
            'motion_analysis':session_analysis(s),'reference':s.get('reference_model'),'reference_source':ref_source,'report':media_url(storage.folder(s['id'])/'physio-report.html'),
            'landmarks':replay_rows(s),'limitations':s.get('limitations',[]),
            'pose_engine':s.get('pose_engine'),'keypoint_model':s.get('keypoint_model'),'detector':s.get('detector'),
            'unavailable_measurements':s.get('unavailable_measurements',unavailable_measurements()),
            'model_checks':s.get('model_checks',{}),'check_in':s.get('patient_check_in'),'ai':s.get('ai',{})}


class ProgramRequest(BaseModel):
    target_repetitions: int = Field(ge=1,le=50)


class CheckInRequest(BaseModel):
    """Post-exercise self-report. Every question is optional; nothing is inferred when skipped."""
    pain_during: bool | None = None
    pain_after: int | None = Field(default=None, ge=0, le=10)
    pain_locations: list[Literal['knee','hip','back','ankle','other']] = Field(default_factory=list, max_length=5)
    difficulty: Literal['easy','moderate','hard'] | None = None
    knee_unstable: bool | None = None
    swelling: bool | None = None
    notes: str = Field(default='', max_length=1000)


class FeedbackRequest(BaseModel):
    text: str = Field(max_length=5000)


class WorkoutCheckInRequest(CheckInRequest):
    session_ids: list[str] = Field(min_length=1, max_length=50)


class AiRequest(BaseModel):
    consent: bool = False
    lang: Literal['en','ar'] = 'en'
    question: str = Field(default='', max_length=500)


class CheckRequest(BaseModel):
    consent: bool = False


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
    seed_reference(library)
    app=FastAPI(title='Wathba',docs_url=None,redoc_url=None)
    # Cross-origin isolation lets ONNX Runtime Web use multi-threaded WebAssembly
    # (SharedArrayBuffer). All app resources are same-origin. Remote-storage mode
    # redirects media to another origin, so isolation stays off there.
    isolate=os.getenv('WATHBA_CROSS_ORIGIN_ISOLATION','0' if remote.enabled() else '1')=='1'

    @app.middleware('http')
    async def performance_headers(request:Request,call_next):
        response=await call_next(request)
        if isolate:
            response.headers.setdefault('Cross-Origin-Opener-Policy','same-origin')
            response.headers.setdefault('Cross-Origin-Embedder-Policy','require-corp')
            response.headers.setdefault('Cross-Origin-Resource-Policy','same-origin')
        if request.url.path.startswith('/vendor/') and response.status_code==200:
            # Runtime and weights are pinned by SHA256 (assets/vendor/manifest.json); cache for a week.
            response.headers['Cache-Control']='public, max-age=604800'
        return response

    @app.get('/')
    def index():return FileResponse(BASE/'web/index.html')

    @app.get('/api/config')
    def config(exercise: str = "squat"):
        if exercise not in ("squat", "jump"):raise HTTPException(400,"Choose Squats or Jump.")
        ref=reference_id(exercise)
        m=storage.load_reference(ref) if ref else None
        legacy=None if ref else legacy_reference_source(exercise)
        teacher=Path(storage.load(ref)['source_video']) if ref else legacy or library/f'therapist-{exercise}.mp4'
        poster=teacher.parent/f'therapist-{exercise}.jpg'
        legacy_poster=teacher.parent/'therapist.jpg'
        if remote.enabled() and not remote.exists(poster) and remote.exists(legacy_poster):poster=legacy_poster
        if remote.enabled() and not poster.exists() and remote.exists(poster):remote.ensure(poster)
        if teacher.exists() and not poster.exists():
            cap=cv2.VideoCapture(str(teacher));cap.set(cv2.CAP_PROP_POS_MSEC,1500);ok,frame=cap.read();cap.release()
            if ok:cv2.imwrite(str(poster),frame)
        return {'exercise':'Squat' if exercise=='squat' else 'Jump','exerciseId':exercise,'comparisonAvailable':bool(m),'side':'Left','view':'Front','target':storage.load_plan().target_repetitions,'model':'YOLOv8n-pose + MoveNet SinglePose Lightning (browser)',
                'referenceAsset':'legacy-reference' if legacy else 'therapist','referenceNeedsRefit':bool(legacy),'referenceLocked':reference_locked(),
                'pose':{'pipeline':PIPELINE,'maxHz':env_number('WATHBA_POSE_MAX_HZ',15,2,30),'reacquireSeconds':env_number('WATHBA_POSE_REACQUIRE_SECONDS',1,.25,10),
                        'models':{k:{f:v[f] for f in ('label','role','runtime','license')} for k,v in MODELS.items()},
                        'vitpose':dict(zip(('available','reason'),vitpose_service.available()))},
                'ai':ai_coach.status(),
                'referenceId':ref,'referenceModel':m,'referenceUrl':media_url(teacher) if teacher.exists() or (remote.enabled() and remote.exists(teacher)) else None,
                'sampleUrl':media_url(library/f'patient-{exercise}.mp4') if (library/f'patient-{exercise}.mp4').exists() or (remote.enabled() and remote.exists(library/f'patient-{exercise}.mp4')) else None,
                'maxUploadMb':int(os.getenv('WATHBA_MAX_UPLOAD_MB','300')),'maxRecordingSeconds':int(os.getenv('WATHBA_MAX_RECORDING_SECONDS','180')),'cameraBitrate':int(os.getenv('WATHBA_CAMERA_BITRATE','1500000')),
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
            await run_in_threadpool(subprocess.run,[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-i',str(raw),'-t','181','-an',
                            '-vf',"scale='min(854,iw)':'min(854,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
                            '-c:v','libx264','-preset','ultrafast','-crf','26','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],
                            check=True,capture_output=True,timeout=120)
            cap,_,duration=open_video(target);cap.release()
        except (ValueError,subprocess.SubprocessError) as exc:
            target.unlink(missing_ok=True);raise HTTPException(400,'Could not read the recording. Use an MP4/MOV or a camera recording under three minutes.') from exc
        finally:raw.unlink(missing_ok=True)
        remote.persist_file(target)
        return {'asset':upload_id,'url':media_url(target),'duration':duration}

    @app.post('/api/process')
    def process(request: TrackingRequest, http: Request):
        if not request.consent:raise HTTPException(400,'Confirm permission to analyse this recording.')
        if request.reference and reference_locked():raise HTTPException(403,'The therapist reference is locked on this public demo.')
        if request.asset in ('therapist','patient'):
            source=library/f'{request.asset}-{request.exercise}.mp4'
            if request.reference != (request.asset=='therapist'):raise HTTPException(400,'Reference and patient sources must be separate.')
        elif request.asset=='legacy-reference':
            # Re-fit a reference prepared by the removed MediaPipe engine from its own source video.
            source=legacy_reference_source(request.exercise)
            if not request.reference or source is None:raise HTTPException(400,'No earlier therapist reference needs to be prepared again.')
        else:
            if len(request.asset)!=32 or any(c not in '0123456789abcdef' for c in request.asset):raise HTTPException(400,'Invalid recording.')
            source=storage.root()/'uploads'/request.asset/'source.mp4'
        if remote.enabled() and not source.exists():remote.ensure(source)
        if not source.exists():raise HTTPException(404,'Recording not found. Upload it again.')
        with LOCK:
            try:
                requested=request.reference_id if known_reference(request.reference_id) else None
                ref=None if request.reference else requested or reference_id(request.exercise)
                if not request.reference and not ref and request.exercise=='squat':raise ValueError('Prepare the therapist reference before analysing the patient.')
                s=process_browser_video(source,request.rows,ref,request.reference,
                                        f'Therapist {request.exercise} demonstration' if request.reference else f'Patient {request.exercise} session', exercise=request.exercise)
                if request.reference:
                    target=storage.root()/('browser-reference.json' if request.exercise=='squat' else 'browser-reference-jump.json')
                    temporary=target.with_suffix('.tmp')
                    temporary.write_text(json.dumps({'id':s['id']}), encoding='utf-8')
                    temporary.replace(target)
                    remote.persist_session(s['id']);remote.persist_file(target)
                    return {'id':s['id'],'model':storage.load_reference(s['id'])}
                remote.persist_session(s['id'])
                return session_response(http,s)
            except ValueError as exc:raise HTTPException(400,str(exc)) from exc

    @app.get('/api/session/{session_id}')
    def session(session_id:str, http: Request):
        try:s=storage.load(session_id)
        except (OSError,ValueError):raise HTTPException(404,'Session not found.')
        return session_response(http,s,**({'cache-control':'private, max-age=86400'} if s.get('kind')=='reference' else {}))

    @app.post('/api/program')
    def update_program(request: ProgramRequest):
        from dataclasses import replace
        plan=replace(storage.load_plan(),target_repetitions=request.target_repetitions)
        storage.save_plan(plan)
        return {'target_repetitions':plan.target_repetitions}

    @app.post('/api/session/{session_id}/check-in')
    def update_check_in(session_id:str,request: CheckInRequest):
        try:
            s=storage.check_in(session_id,{**request.model_dump(),'pain_locations':list(dict.fromkeys(request.pain_locations)),'notes':request.notes.strip()})
            remote.persist_session(session_id)
            return public_session(s)
        except (OSError,ValueError):raise HTTPException(404,'Session not found.')

    @app.post('/api/workout/check-in')
    def update_workout_check_in(request: WorkoutCheckInRequest):
        answers=request.model_dump(exclude={'session_ids'})
        answers.update(pain_locations=list(dict.fromkeys(request.pain_locations)),notes=request.notes.strip())
        try:
            sessions=storage.workout_check_in(request.session_ids,answers)
        except (OSError,ValueError) as exc:
            raise HTTPException(400,'All workout recordings must exist and belong to patient exercises.') from exc
        for session in sessions:remote.persist_session(session['id'])
        return {'session_ids':[s['id'] for s in sessions],'check_in':sessions[-1]['patient_check_in']}

    @app.post('/api/session/{session_id}/feedback')
    def update_feedback(session_id:str,request: FeedbackRequest):
        try:
            s=storage.feedback(session_id,request.text)
            remote.persist_session(session_id)
            return public_session(s)
        except (OSError,ValueError):raise HTTPException(404,'Session not found.')

    @app.post('/api/session/{session_id}/vitpose-check')
    def vitpose_check(session_id:str,request:CheckRequest):
        """Optional server-side ViTPose check of selected frames of an already uploaded recording."""
        if not request.consent:raise HTTPException(400,'Confirm that this recording may be re-analysed on the Wathba server.')
        ok,reason=vitpose_service.available()
        if not ok:raise HTTPException(503,reason)
        try:s=storage.load(session_id)
        except (OSError,ValueError):raise HTTPException(404,'Session not found.')
        if s.get('pose_engine')!=PIPELINE:raise HTTPException(400,'This session was recorded with an earlier pose engine and has no tracked person boxes.')
        if remote.enabled():remote.ensure(s['source_video'])
        try:result=vitpose_service.check_session(s)
        except vitpose_service.Unavailable as exc:raise HTTPException(503,str(exc)) from exc
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc
        with storage.LOCK:
            latest=storage.load(session_id)
            latest.setdefault('model_checks',{})['vitpose']=result
            storage.save(latest)
        remote.persist_session(session_id)
        return result

    def run_ai(session_id, request, kind, work):
        """Shared consent, availability and storage handling for the Qwen3 features."""
        if not request.consent:raise HTTPException(400,'Confirm that this session may be processed by the Qwen3 model on the Wathba server.')
        ok,reason=llm.available('vision' if kind=='vision' else 'text')
        if not ok:raise HTTPException(503,reason)
        try:s=storage.load(session_id)
        except (OSError,ValueError):raise HTTPException(404,'Session not found.')
        if kind=='vision' and remote.enabled():remote.ensure(s['source_video'])
        try:result=work(s)
        except llm.Unavailable as exc:raise HTTPException(503,str(exc)) from exc
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc
        with storage.LOCK:
            latest=storage.load(session_id);store=latest.setdefault('ai',{})
            if kind=='summary':store.setdefault('summary',{})[request.lang]=result
            elif kind=='question':store['questions']=[*store.get('questions',[]),result][-20:]
            else:store['vision']=result
            storage.save(latest)
        remote.persist_session(session_id)
        return result

    @app.post('/api/session/{session_id}/ai/summary')
    def ai_summary(session_id:str,request:AiRequest):
        return run_ai(session_id,request,'summary',lambda s:ai_coach.summary(s,request.lang))

    @app.post('/api/session/{session_id}/ai/ask')
    def ai_ask(session_id:str,request:AiRequest):
        return run_ai(session_id,request,'question',lambda s:ai_coach.answer(s,request.question,request.lang))

    @app.post('/api/session/{session_id}/ai/vision')
    def ai_vision(session_id:str,request:AiRequest):
        return run_ai(session_id,request,'vision',lambda s:ai_coach.review_frames(s,request.lang))

    @app.get('/api/history')
    def history():
        return [{'id':s['id'],'repetitions':s['repetitions'],'score':s.get('match_score',{}).get('value'),'created':s['created_at'],'exercise':s['exercise'],'coverage':s['coverage'],'duration':s['duration'],
                 'pain':(s.get('patient_check_in') or {}).get('pain_after'),'attention':(s.get('patient_check_in') or {}).get('attention',[])}
                for s in storage.sessions() if s.get('pose_engine') in SESSION_ENGINES and s.get('height_normalisation')=='static_torso_v1' and s.get('kind')!='reference' and not s.get('internal_validation')][:100]

    @app.get('/api/training-summary')
    def training_summary():
        """Days, weeks and months with at least one recorded patient session (all sessions, not only the last 100)."""
        from .program import training_summary as summarise
        return summarise([s for s in storage.sessions() if s.get('pose_engine') in SESSION_ENGINES
                          and s.get('kind')!='reference' and not s.get('internal_validation')])

    @app.get('/api/demo-program')
    def demo_program():
        from .program import demo_program as build_program
        sessions=[s for s in storage.sessions() if s.get('pose_engine') in SESSION_ENGINES
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
            # Saved videos and pictures never change, so a browser can keep them.
            return FileResponse(target,headers={'Cache-Control':'private, max-age=86400'} if target.suffix in ('.mp4','.jpg') else None)
        except (OSError,ValueError):raise HTTPException(404,'Media not found.')

    app.mount('/static',StaticFiles(directory=BASE/'web'),name='static')
    app.mount('/assets',StaticFiles(directory=BASE/'assets'),name='assets')
    app.mount('/vendor',StaticFiles(directory=BASE/'assets/vendor'),name='vendor')
    if not remote.enabled():app.mount('/media',StaticFiles(directory=storage.root()),name='media')
    return app
