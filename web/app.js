import {Workout} from '/static/workout.js';
import {icon,setIcon} from '/static/icons.js';
import {PoseEngine} from '/static/pose/engine.js';
import {CONFIG as POSE,EDGES,MODELS,joint,toDisplay} from '/static/pose/schema.js';
import {RepCounter} from '/static/rep-counter.js';
import {repetitionSummary} from '/static/rep-summary.js';
import {AudioCoach} from '/static/audio-coach.js';
import {SpeechCoach} from '/static/speech-coach.js';
import {evaluateLive,colourForEdge,measurements,liveTone} from '/static/motion-coach.js';
import {initI18n,currentLang} from '/static/i18n.js';
initI18n();
const $=id=>document.getElementById(id);
const motion=$('motion'),canvas=$('skeleton'),ctx=canvas.getContext('2d'),mini=$('reference-mini');
const state={config:null,referenceRows:[],referenceCycles:[],rows:[],session:null,mode:'reference',asset:null,stream:null,recorder:null,chunks:[],tracking:false,job:0,replay:[],liveReps:0,recordStart:0,lastSample:-1,mirrored:false};
// Joints the frontal squat measurement needs (shoulders, hips, ankles); named, model-independent.
const REQUIRED=POSE.measurementRequirements.hip_height;
const DRAWN=new Set(EDGES.flat());
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clock=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
let engine,liveHandle,paintHandle,toastTimer;
const repCounter=new RepCounter(),audioCoach=new AudioCoach(),speechCoach=new SpeechCoach(),workout=new Workout();
const coachBanner=document.querySelector('.coach-banner');
const continueExercises=document.createElement('button');
continueExercises.type='button';continueExercises.className='secondary';continueExercises.textContent='Continue exercises';
continueExercises.onclick=()=>{cleanup();page('home');};$('show-summary').after(continueExercises);
const soundButton=document.createElement('button');
soundButton.type='button';soundButton.className='secondary';soundButton.id='sound-alerts';
function soundLabel(){soundButton.textContent=audioCoach.enabled?'Voice and sound: on':'Voice and sound: muted';soundButton.setAttribute('aria-pressed',String(audioCoach.enabled));}
const countStatus=document.createElement('p');countStatus.id='rep-count-status';countStatus.className='subtle';document.querySelector('.live-summary').after(countStatus);
const soundControls=document.createElement('div');
soundControls.className='exercise-options';soundControls.append(soundButton);
const testSoundButton=document.createElement('button');
testSoundButton.type='button';testSoundButton.className='secondary';testSoundButton.id='test-sound';testSoundButton.textContent='Test sound';
soundControls.append(testSoundButton);
testSoundButton.onclick=async()=>{if(!await audioCoach.preview())toast('Sound could not start on this browser.');speechCoach.stop();speechCoach.say(currentLang()==='ar'?'استمر':'Keep going');};
soundLabel();$('stage').before(soundControls);
const sampleButton=document.createElement('button');
sampleButton.type='button';sampleButton.className='secondary';sampleButton.id='use-sample';sampleButton.textContent='Try sample video';sampleButton.hidden=true;$('upload-video').after(sampleButton);
soundButton.onclick=async()=>{audioCoach.enabled=!audioCoach.enabled;speechCoach.enabled=audioCoach.enabled;soundLabel();if(!audioCoach.enabled)stopCoaching();else if(!await audioCoach.preview())toast('Sound could not start on this browser.');};
const stopCoaching=()=>{audioCoach.stop();speechCoach.stop();};
function startVoice(){if(!audioCoach.enabled)return;speechCoach.unlock();if(currentLang()==='ar'&&speechCoach.missing('ar'))toast('Arabic voice is not available on this device. Comments stay on screen.');}
// Waits one tick so the Arabic translation of the comment is what gets read out.
function speakComment(urgent){setTimeout(()=>{if(state.tracking||state.mode==='analysing')speechCoach.say($('live-hint').textContent,{urgent});},0);}
function resetLive(){delete coachBanner.dataset.tone;repCounter.reset();state.liveTorsoScale=null;state.liveParts=null;state.floorPosition=null;}
function acceptedReps(s){return s.accepted_repetitions??s.cycles.filter(c=>c.accepted===true).length;}

// Notifications: dismiss with the close button, a tap on the message or Escape; auto-hide pauses while hovered/focused.
function hideToast(){clearTimeout(toastTimer);$('toast').hidden=true;}
function scheduleToastHide(ms){clearTimeout(toastTimer);toastTimer=setTimeout(hideToast,ms);}
function toast(message){
 const el=$('toast'),text=document.createElement('span'),close=document.createElement('button');
 text.className='toast-text';text.textContent=message;
 close.type='button';close.className='toast-close';close.setAttribute('aria-label','Dismiss notification');close.innerHTML=icon('xmark');
 close.onclick=event=>{event.stopPropagation();hideToast();};
 el.replaceChildren(text,close);el.hidden=false;scheduleToastHide(6000);
}
$('toast').addEventListener('click',hideToast);
for(const [event,ms] of [['mouseenter',null],['focusin',null],['mouseleave',3000],['focusout',3000]])$('toast').addEventListener(event,()=>ms?(!$('toast').hidden&&scheduleToastHide(ms)):clearTimeout(toastTimer));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('toast').hidden&&!document.querySelector('dialog[open]'))hideToast();});
function resetScroll(){window.scrollTo(0,0);document.querySelector('main')?.scrollTo(0,0);}
function page(name){for(const el of document.querySelectorAll('.page'))el.hidden=el.id!==name;document.body.classList.toggle('work-mode',name==='work');resetScroll();cancelAnimationFrame(referenceHandle);if(name==='work')referenceHandle=requestAnimationFrame(paintReference);if(name!=='work'){motion.pause();mini.pause();cancelAnimationFrame(paintHandle);}window.dispatchEvent(new CustomEvent('wathba:page',{detail:name}));}
function busy(title,text='',value=0){$('busy').hidden=false;$('busy-title').textContent=title;$('busy-text').textContent=text;$('busy-progress').value=value;}
function hideBusy(){$('busy').hidden=true;}
const pendingReads=new Map();
function api(url,options){if(options)return request(url,options);/* Screens that open together share one read. */if(!pendingReads.has(url))pendingReads.set(url,request(url).finally(()=>pendingReads.delete(url)));return pendingReads.get(url);}
async function request(url,options){const r=await fetch(url,options);if(!r.ok){let v=await r.json().catch(()=>({detail:r.statusText}));throw Error(typeof v.detail==='string'?v.detail:'The recording could not be processed. Please try again.');}return r.json();}
function post(url,data){return api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});}
async function playSafe(video){try{await video.play();}catch(error){if(error.name!=='AbortError')throw error;}}
async function loadVideo(video,url){video.pause();video.crossOrigin='anonymous';video.src=url;video.load();if(video.readyState>=2)return;await new Promise((resolve,reject)=>{video.addEventListener('loadeddata',resolve,{once:true});video.addEventListener('error',()=>reject(Error('This video could not be played. Try an MP4 recording.')),{once:true});});}
async function seek(video,t){t=Math.min(t,Math.max(0,video.duration-.045));if(Math.abs(video.currentTime-t)<.002&&video.readyState>=2)return;await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Video seeking timed out. Try a shorter MP4.')),12000);video.addEventListener('seeked',()=>{clearTimeout(timer);resolve();},{once:true});video.currentTime=t;});}

// ---------------------------------------------------------------- pose engine
function showPoseStatus(s){
 const el=$('pose-model');if(!el)return;
 const thread=s.thread==='worker'?'background worker':s.thread==='main'?'page thread':s.thread;
 const parts=[s.keypointLabel?`${s.keypointLabel} keypoints`:'No keypoint model',s.detector?`${s.detector} person selection`:null].filter(Boolean);
 el.textContent=`${parts.join(' · ')}${s.degraded.length?' · degraded':''}`;
 el.title=[`Inference: ${thread}`,s.latencyMs?`Latency ≈ ${Math.round(s.latencyMs)} ms`:'',...s.degraded].filter(Boolean).join('\n');
 el.classList.toggle('degraded',s.degraded.length>0);el.hidden=false;
}
function poseEvent(e){
 // A different person or keypoint model starts a new temporal context for live counting.
 if(['reset','track-change','model-change'].includes(e.type)){state.baseline=null;state.phase='rest';resetLive();}
}
async function ensureEngine(){
 if(!engine){
  const pose=state.config?.pose||{},lowEnd=(navigator.hardwareConcurrency||8)<=4||(navigator.deviceMemory||8)<=4;
  engine=new PoseEngine({config:{maxHz:lowEnd?Math.min(8,pose.maxHz||15):pose.maxHz,reacquireSeconds:pose.reacquireSeconds},onStatus:showPoseStatus,onEvent:poseEvent});
 }
 try{await engine.init();}catch(error){throw Error(`Body tracking could not start on this device: ${error.message}`);}
 return engine;
}
/** One schema row for the backend. Unavailable frames are explicit nulls, never zeros. */
function rowFrom(result,time){
 const p=result.status==='ok'?result.pose:null;
 return p?{schema:p.schema,time,frameId:p.frameId,trackId:p.trackId,model:p.model,detector:p.detector,keypoints:p.keypoints,box:p.box}
  :{time,keypoints:null,model:null,trackId:null,reason:result.reason||result.status};
}
const thresholdOf=p=>p?.threshold??(MODELS[p?.model]?.keypointThreshold);
const usable=(p,name)=>{if(!p?.keypoints)return null;const k=p.keypoints[name];const limit=thresholdOf(p);return k&&limit!==undefined&&k.confidence>=limit?k:null;};

function drawOn(surface,video,pose,mirrored=false,fit='contain'){
 const box=surface.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);if(!box.width||!box.height)return;
 if(surface.width!==Math.round(box.width*dpr)||surface.height!==Math.round(box.height*dpr)){surface.width=Math.round(box.width*dpr);surface.height=Math.round(box.height*dpr);}
 const brush=surface.getContext('2d');brush.setTransform(dpr,0,0,dpr,0,0);brush.clearRect(0,0,box.width,box.height);if(!pose?.keypoints)return;
 const vw=video.videoWidth||464,vh=video.videoHeight||832,scale=(fit==='cover'?Math.max:Math.min)(box.width/vw,box.height/vh),w=vw*scale,h=vh*scale,x=(box.width-w)/2,y=(box.height-h)/2;
 // Mirroring is a display transform only; anatomical joint names are unchanged.
 const at=name=>{const k=toDisplay(usable(pose,name),mirrored);return k&&{x:x+k.x*w,y:y+k.y*h};};
 brush.lineWidth=1.7;brush.strokeStyle='#a5ffcc';brush.shadowColor='#9bffb8';brush.shadowBlur=4;
 for(const[a,b]of EDGES){const p=at(a),q=at(b);if(!p||!q)continue;brush.strokeStyle=state.mode==='recording'&&surface===canvas?colourForEdge(a,b,pose,state.liveParts):'#a5ffcc';brush.beginPath();brush.moveTo(p.x,p.y);brush.lineTo(q.x,q.y);brush.stroke();}
 for(const name of DRAWN){const p=at(name);if(!p)continue;brush.fillStyle=/knee|ankle|hip/.test(name)?'#c6ff9b':'#c5ffdd';brush.beginPath();brush.arc(p.x,p.y,3.3,0,2*Math.PI);brush.fill();}
}
function draw(pose){drawOn(canvas,motion,pose,state.mirrored,document.body.classList.contains('camera-full')?'cover':'contain');if(state.mode!=='reference'){
 const count=REQUIRED.filter(n=>usable(pose,n)).length;
 $('tracking-quality').textContent=pose?.keypoints?`${Math.round(count/REQUIRED.length*100)}%`:'—';
}}
let referenceHandle;
function paintReference(){
 if($('work').hidden)return;
 if(state.mode==='replay'&&state.referenceCycles.length&&state.session){
  const t=motion.currentTime,c=state.session.cycles.find(c=>t>=c.start&&t<=c.end),r=state.referenceCycles[0];
  let target=r.start;
  if(c){target=t<=c.peak_time?r.start+(t-c.start)/(c.peak_time-c.start)*(r.peak_time-r.start):r.peak_time+(t-c.peak_time)/(c.end-c.peak_time)*(r.end-r.peak_time);}
  else if(state.session.cycles.some(c=>c.end<t))target=r.end;
  if(mini.readyState>=2&&!mini.seeking&&Math.abs(mini.currentTime-target)>.055)mini.currentTime=target;
 }
 drawOn($('reference-skeleton'),mini,poseAt(state.referenceRows,mini.currentTime));referenceHandle=requestAnimationFrame(paintReference);
}
/** Replay pose at time t: interpolate only between rows of the same model and person. */
function poseAt(rows,t){
 if(!rows.length)return null;let lo=0,hi=rows.length-1;while(lo<hi){const m=Math.ceil((lo+hi)/2);if(rows[m].time<=t)lo=m;else hi=m-1;}
 const a=rows[lo],b=rows[lo+1];
 if(a?.keypoints&&b?.keypoints&&a.model===b.model&&a.trackId===b.trackId&&b.time-a.time<.4){
  const f=Math.max(0,Math.min(1,(t-a.time)/(b.time-a.time))),keypoints={};
  for(const[name,k]of Object.entries(a.keypoints)){const n=b.keypoints[name];keypoints[name]=k&&n?{x:k.x*(1-f)+n.x*f,y:k.y*(1-f)+n.y*f,z:null,confidence:Math.min(k.confidence,n.confidence)}:null;}
  return {...a,keypoints};
 }
 return a;
}
function paintReplay(){draw(poseAt(state.replay,motion.currentTime));$('video-time').textContent=clock(motion.currentTime);if(motion.duration&&Number.isFinite(motion.duration))$('seek').value=Math.round(motion.currentTime/motion.duration*1000);if(state.mode==='replay'&&state.session){const scores=new Map((state.session.match_score?.per_repetition||[]).map(r=>[r.rep,r.value]));const n=state.session.cycles.filter(c=>c.comparison_assessable!==false&&scores.get(c.rep)>=60&&c.end<=motion.currentTime).length;setReps(n);const completed=state.session.cycles.filter(c=>c.end<=motion.currentTime).at(-1);$('tempo-value').textContent=completed?`${completed.duration.toFixed(1)}s`:'—';}paintHandle=requestAnimationFrame(paintReplay);}
function setReps(n){const total=state.mode==='replay'?(state.session?.target||5):(state.config?.target||5);$('live-reps').textContent=Math.min(total,n);$('rep-progress').style.height=`${Math.min(100,n/total*100)}%`;}
async function extractVideo(video,job,onProgress,stepMs=0){
 const tracker=await ensureEngine(),duration=video.duration;
 if(!Number.isFinite(duration)||duration>180||duration<1)throw Error('Use a video between one second and three minutes.');
 // One keypoint model per recording: if a model fails mid-way, restart with the fallback model.
 for(let attempt=0;attempt<2;attempt++){
  tracker.resetTracking('new recording');const model=tracker.keypointModel,rows=[];let restart=false,lastResult=null;if(video===motion&&state.mode==='analysing'){repCounter.accepted=0;repCounter.counted=0;repCounter.observed=0;resetLive();}
  const step=async t=>{if(job!==state.job)throw new DOMException('Cancelled','AbortError');await seek(video,t);if(job!==state.job)throw new DOMException('Cancelled','AbortError');const r=await tracker.estimate(video,video.currentTime);if(job!==state.job)throw new DOMException('Cancelled','AbortError');rows.push(rowFrom(r,+video.currentTime.toFixed(5)));draw(r.pose);if(tracker.keypointModel!==model)restart=true;lastResult=r;return r;};
  for(let t=0;t<duration-.045&&!restart;t+=1/6){const began=performance.now(),result=await step(t);onProgress?.(t/duration,video.currentTime,rows,result);await new Promise(r=>setTimeout(r,Math.max(0,stepMs-(performance.now()-began))));}
  if(!restart&&rows.length&&duration-rows.at(-1).time>.13)await step(duration-.05);
  if(!restart){if(video===motion&&state.mode==='analysing'&&lastResult)liveResult(lastResult,rows.at(-1).time,true);return rows;}
  if(!tracker.keypointModel)break;
 }
 throw Error('Body tracking stopped working on this device. Reload the page and try again.');
}
async function ensureReference(job){if(state.config.referenceId){if(state.referenceLoadedId!==state.config.referenceId){const s=await api(`/api/session/${state.config.referenceId}`);state.referenceRows=s.landmarks;state.referenceCycles=s.cycles;state.referenceLoadedId=s.id;}return;}if(!state.config.referenceUrl)throw Error('A therapist demonstration is needed before this session can start.');busy('Preparing the therapist reference',state.config.referenceNeedsRefit?'The reference was prepared with the previous pose engine and is being tracked again.':'Tracking the actual therapist recording in this browser.');const v=document.createElement('video');v.muted=true;v.playsInline=true;v.preload='auto';await loadVideo(v,state.config.referenceUrl);const rows=await extractVideo(v,job,(p)=>busy('Preparing the therapist reference','Learning movement and timing from the therapist’s recording.',p));const result=await post('/api/process',{asset:state.config.referenceAsset||'therapist',reference:true,consent:true,rows});state.config.referenceId=result.id;state.config.referenceModel=result.model;state.config.referenceNeedsRefit=false;state.referenceRows=rows;const prepared=await api(`/api/session/${result.id}`);state.referenceRows=prepared.landmarks;state.referenceCycles=prepared.cycles;state.referenceLoadedId=prepared.id;v.remove();hideBusy();}
// Camera and live recording fill the screen (and use browser fullscreen where allowed).
let dockObserver;
function setCameraFull(on){
 if(on&&!document.body.classList.contains('camera-full'))resetScroll();
 document.body.classList.toggle('camera-full',on);
 if(on)document.querySelector('.work-dock').prepend(soundControls);
 else $('stage').before(soundControls);
 if(on)mini.pause(); // the doctor's video is hidden in full-screen camera
 if(on&&!dockObserver&&window.ResizeObserver){dockObserver=new ResizeObserver(([e])=>document.body.style.setProperty('--dock-h',`${Math.round(e.target.getBoundingClientRect().height)}px`));dockObserver.observe(document.querySelector('.work-dock'));}
 if(!on&&document.fullscreenElement)document.exitFullscreen?.().catch(()=>{});
}
// Browser fullscreen only when the app already spans the screen (phones); on desktop the camera fills the app's phone frame.
function requestFullscreen(){try{const shell=document.querySelector('.app-shell');if(shell&&shell.getBoundingClientRect().width<innerWidth-2)return;if(!document.fullscreenElement)document.documentElement.requestFullscreen?.({navigationUI:'hide'})?.catch(()=>{});}catch{}}
function inputState(mode){state.mode=mode;setCameraFull(['camera','recording'].includes(mode));$('work').dataset.mode=mode;$('stage-pause').setAttribute('aria-label',mode==='recording'?'Pause session':'Pause video');$('camera-empty').hidden=mode!=='reference';$('patient-label').textContent=mode==='reference'?'You':mode==='replay'?'Your recording':'You';$('patient-caption').textContent=mode==='recording'?'Live body tracking':mode==='replay'?'Detected joints · original timing':mode==='analysing'?'Analysing your movement':'Your recording';$('reference-timing').textContent=mode==='replay'?'Matched repetition phase':'Movement guide';$('guide-pause').hidden=mode==='replay';$('stage-pause').hidden=['reference','camera','analysing'].includes(mode);$('input-actions').hidden=mode==='recording'||mode==='replay'||mode==='analysing';$('record').hidden=mode!=='camera';$('analyse').hidden=mode!=='upload';$('finish').hidden=mode!=='recording';$('toggle-view').hidden=['reference','camera','upload'].includes(mode);$('playback-controls').hidden=mode!=='replay';$('cancel-analysis').hidden=mode!=='analysing';$('rep-caption').textContent=mode==='replay'?'Reps at 60%+ played':'Reps at 60%+';$('coach-title').textContent=mode==='replay'?'Review together':mode==='recording'?'Keep going':'Let’s begin';}
function setMirrored(on){state.mirrored=on;$('stage').classList.toggle('mirrored',on);}
function cleanup(){stopCoaching();resetLive();state.job++;setCameraFull(false);state.tracking=false;engine?.resetTracking('cleanup');cancelAnimationFrame(liveHandle);cancelAnimationFrame(paintHandle);if(state.recorder&&state.recorder.state!=='inactive'){state.recorder.onstop=null;state.recorder.stop();}state.stream?.getTracks().forEach(t=>t.stop());state.stream=null;motion.srcObject=null;motion.pause();mini.pause();setMirrored(false);hideBusy();}
const referenceReady=()=>Boolean(state.referenceVideo&&state.referenceLoadedId===state.config?.referenceId);
function adoptConfig(config){if(config.referenceId!==state.config?.referenceId&&state.referenceVideo){URL.revokeObjectURL(state.referenceVideo);state.referenceVideo=null;}state.config=config;sampleButton.hidden=!config.sampleUrl;}
/** Fetch the demonstration before it is asked for, so opening an exercise does not wait on the network. */
async function preloadReference(){const{referenceId,referenceUrl}=state.config;if(!referenceId||!referenceUrl||navigator.connection?.saveData)return;try{await ensureReference(state.job);const r=await fetch(referenceUrl);if(!r.ok)return;const video=await r.blob();if(state.config.referenceId===referenceId)state.referenceVideo=URL.createObjectURL(video);}catch(error){console.warn('Reference preload failed; it will load when needed.',error.message);}}
async function startWorkout(){
 cleanup();page('work');setReps(0);$('tracking-quality').textContent='—';$('tempo-value').textContent='—';$('stage').classList.remove('skeleton-only');$('toggle-view').setAttribute('aria-label','Switch to skeleton view');setIcon($('toggle-view'),'accessibility');
 $('rep-note').textContent='Your set starts when you’re ready.';$('live-reps').nextElementSibling.textContent=`/${state.config?.target||5}`;$('live-hint').textContent='Watch the movement. Get ready at your own pace.';$('tracking-status').textContent='Preparing demonstration';inputState('reference');
 const controls=[$('use-camera'),$('upload-video'),sampleButton];controls.forEach(b=>b.disabled=true);const job=state.job;
 try{
  await Promise.race([state.referencePreload,new Promise(r=>setTimeout(r,3000))]);if(job!==state.job)return;
  // A restart can replace the reference while a tab stays open; a preloaded one starts now and is checked alongside.
  const latest=api('/api/config');if(!referenceReady())await adoptConfig(await latest);else latest.then(adoptConfig).catch(()=>{});
  await ensureReference(job);if(job!==state.job)return;
  const url=referenceReady()?state.referenceVideo:state.config.referenceUrl;
  try{await loadVideo(motion,url);}catch(error){if(url===state.config.referenceUrl)throw error;state.referenceVideo=null;await loadVideo(motion,state.config.referenceUrl);}if(job!==state.job)return;
  mini.src=motion.currentSrc||motion.src;await playSafe(mini);if(job!==state.job)return;
  state.replay=state.referenceRows;motion.loop=true;await playSafe(motion);if(job!==state.job)return;
  $('tracking-status').textContent='Therapist reference';$('live-hint').textContent='Watch your therapist, then start your set.';paintReplay();
 }catch(error){hideBusy();if(job===state.job&&error.name!=='AbortError')toast(error.message);}
 finally{controls.forEach(b=>b.disabled=false);}
}
async function chooseCamera(){requestFullscreen();try{cleanup();inputState('camera');$('record').disabled=true;state.stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:state.config?.maxRecordingSeconds<180?480:720},height:{ideal:state.config?.maxRecordingSeconds<180?854:1280}},audio:false});motion.removeAttribute('src');motion.srcObject=state.stream;motion.loop=false;setMirrored(true);await playSafe(motion);draw(null);$('tracking-status').textContent='Camera ready';$('live-hint').textContent='Keep your whole body and feet in view.';$('record').disabled=false;}catch(error){$('record').disabled=false;inputState('reference');toast(error.name==='NotAllowedError'?'Camera permission was denied. Allow it in your browser or upload a video.':error.message);}}
async function uploadFile(file){if(!file)return;const limit=state.config?.maxUploadMb||300;if(file.size>limit*1024*1024)throw Error(`This demo supports videos up to ${limit} MB. Use a short clip or the provided patient video.`);const form=new FormData();form.append('file',file);return api('/api/upload',{method:'POST',body:form});}
async function chooseUpload(file){cleanup();const job=state.job;busy('Preparing your recording','Reading the video and setting up browser tracking.');try{const uploaded=await uploadFile(file);if(job!==state.job)return;state.asset=uploaded.asset;inputState('upload');await loadVideo(motion,uploaded.url);motion.loop=false;playSafe(mini).catch(error=>toast(error.message));draw(null);$('tracking-status').textContent='Patient video ready';$('live-hint').textContent='Ready to analyse your uploaded set.';}finally{hideBusy();}}
async function chooseSample(){cleanup();const job=state.job;busy('Preparing your recording','Loading the sample patient video.');try{state.asset='patient';inputState('upload');await loadVideo(motion,state.config.sampleUrl);if(job!==state.job)return;motion.loop=false;draw(null);$('tracking-status').textContent='Sample video ready';$('live-hint').textContent='Ready to analyse the sample set.';}finally{hideBusy();}}
const VIEWING_STEP_MS=222; // Three-quarter speed, so the patient can follow the analysis.
async function analyseUpload(options){startVoice();if(audioCoach.enabled&&!await audioCoach.unlock())toast('Sound alerts are unavailable on this browser. Visual feedback remains active.');const job=++state.job;state.pausedAt=null;cancelAnimationFrame(paintHandle);inputState('analysing');setReps(state.liveReps);$('rep-caption').textContent='Reps at 60%+';$('tracking-status').textContent='Tracking in this browser';$('live-hint').textContent='Analysing the uploaded movement…';$('rep-note').textContent='Final repetition count appears after comparison.';try{const rows=await extractVideo(motion,job,(p,t,rows,result)=>{if(result)liveResult(result,t);$('video-time').textContent=clock(t);$('tracking-status').textContent='Analysing video: '+Math.round(p*100)+'%';},options?.paced===false?0:VIEWING_STEP_MS);if(job!==state.job)return;busy('Building your report','Comparing the patient’s movement with the therapist reference and extracting the actual clips.');const s=await post('/api/process',{asset:state.asset,reference:false,reference_id:state.config.referenceId,consent:true,rows});if(job!==state.job)return;workout.remember(s);showResults(s);}catch(error){if(error.name!=='AbortError'){toast(error.message);inputState('upload');}}finally{stopCoaching();hideBusy();$('live-reps').nextElementSibling.textContent=`/${state.config?.target||5}`;}}
/** Frontal pelvic descent in static torso lengths, or null (counting pauses) when joints are unreliable. */
function hipHeight(pose){
 const names=[...REQUIRED,'left_knee','right_knee'];
 const p=Object.fromEntries(names.map(n=>[n,joint(pose,n,{margin:0})]));
 if(names.some(n=>!p[n]||p[n].x<0||p[n].x>1||p[n].y<0||p[n].y>1))return null;
 const w=pose.frame.width,h=pose.frame.height;
 const torso=Math.hypot((p.left_shoulder.x+p.right_shoulder.x-p.left_hip.x-p.right_hip.x)*w/2,(p.left_shoulder.y+p.right_shoulder.y-p.left_hip.y-p.right_hip.y)*h/2);
 const floor=(p.left_ankle.y+p.right_ankle.y)/2;
 if(torso<=5)return null;
 if(state.liveTorsoScale==null){state.liveTorsoScale=torso;state.floorPosition=floor;}
 if(Math.abs(torso/state.liveTorsoScale-1)>.35&&Math.abs(floor-state.floorPosition)>.08){resetLive();return null;}
 return (p.left_ankle.y+p.right_ankle.y-p.left_hip.y-p.right_hip.y)*h/2/state.liveTorsoScale;
}
const liveMessages={
 tracking:'Counting paused: keep your whole body and feet visible.',
 alignment:'This movement differs from the guide. Check your knee and trunk position.',
 range:'This repetition was not counted: match the demonstrated movement range.',
 tempo:'This repetition was not counted: follow the demonstrated pace.',
 reference:'Counting needs a matching therapist reference. Prepare the reference for the active pose model.'
};
function liveResult(result,t,finishing=false){
 if((!state.tracking&&state.mode!=='analysing')||state.pausedAt||['busy','stale'].includes(result.status))return;
 if(state.tracking&&t-state.lastSample>=1/6){state.rows.push(rowFrom(result,+t.toFixed(5)));state.lastSample=t;}
 const pose=result.status==='ok'?(result.display||result.pose):null,height=pose?hipHeight(pose):null;
 const model=state.config.referenceModel,compatible=pose?.model===model?.keypoint_model;
 const depth=height!==null&&repCounter.baseline!==null?height-repCounter.baseline:0;
 const feedback=evaluateLive(pose,{model:compatible?model:null,referenceRows:state.referenceRows,referenceCycles:state.referenceCycles,depth,returning:repCounter.active&&-depth<repCounter.active.peak-.03});
 state.liveParts=feedback.parts;draw(pose);
 const values=measurements(pose);
 const features={knee_offset:values.leftKnee,torso_lean:values.trunk};
 const outcome=repCounter.update({time:t,height,parts:feedback.parts,features,finishing,reference:!pose||compatible?model:null,valid:height!==null&&compatible});
 if(height===null&&repCounter.lastTime===null){state.liveTorsoScale=null;state.floorPosition=null;}
 state.liveReps=repCounter.counted;setReps(state.liveReps);
 $('rep-caption').textContent='Reps at 60%+';
 const issue=outcome.issue;
 $('coach-title').textContent=issue?'Check your movement':outcome.calibrating?'Get ready':outcome.completed?'Reference matched':'Keep going';
 audioCoach.update(issue,performance.now()/1000,outcome.completed&&!outcome.accepted);
 if(outcome.completed&&outcome.counted&&issue)$('live-hint').textContent=currentLang()==='ar'?'التكرار اتحسب لأنه وصل إلى 60%، لكن فيه ملاحظات على الأداء.':'Counted at 60% or above, with movement differences to review.';
 else if(issue)$('live-hint').textContent=liveMessages[issue];
 else if(outcome.calibrating)$('live-hint').textContent='Hold the standing start position steady to begin counting.';
 else $('live-hint').textContent=outcome.completed?(outcome.counted?'Repetition reached 60% reference match and was counted.':'This repetition was not counted.'):feedback.message;
 const tone=liveTone(issue,outcome,feedback);coachBanner.dataset.tone=tone;speakComment(tone==='bad'||Boolean(issue));
 if(outcome.completed)$('tempo-value').textContent=outcome.duration.toFixed(1)+'s';
 const counts=currentLang()==='ar'?`المرصود: ${repCounter.observed} · وصل إلى 60%: ${repCounter.counted} · الصحيح: ${repCounter.accepted}`:`Detected: ${repCounter.observed} · At least 60%: ${repCounter.counted} · Correct: ${repCounter.accepted}`;
 if(countStatus.textContent!==counts)countStatus.textContent=counts;
 $('rep-note').textContent=repCounter.accepted+' matched / '+repCounter.observed+' observed - provisional until final analysis';
}
async function startRecording(){if(!state.stream)return;const job=state.job;try{startVoice();if(audioCoach.enabled&&!await audioCoach.unlock())toast('Sound alerts are unavailable on this browser. Visual feedback remains active.');repCounter.accepted=0;repCounter.observed=0;resetLive();busy('Preparing live tracking','The pose models run on this device; video frames are not sent anywhere during tracking.');const tracker=await ensureEngine();if(job!==state.job)return;tracker.resetTracking('new recording');hideBusy();for(let n=3;n>0;n--){$('stage-message').hidden=false;$('stage-message').textContent=n;await new Promise(r=>setTimeout(r,800));if(job!==state.job){$('stage-message').hidden=true;return;}}$('stage-message').hidden=true;const mime=['video/webm;codecs=vp8','video/webm','video/mp4'].find(t=>MediaRecorder.isTypeSupported(t));state.recorder=new MediaRecorder(state.stream,mime?{mimeType:mime,videoBitsPerSecond:state.config?.cameraBitrate||2500000}:{});state.chunks=[];state.rows=[];state.lastSample=-1;state.liveReps=0;state.baseline=null;state.phase='rest';resetLive();state.recorder.ondataavailable=e=>{if(e.data.size)state.chunks.push(e.data);};const started=new Promise((resolve,reject)=>{state.recorder.onstart=resolve;state.recorder.onerror=e=>reject(e.error||Error('Camera recording could not start.'));});state.recorder.start(250);await started;state.recordStart=performance.now();state.pausedAt=null;inputState('recording');state.tracking=true;$('tracking-status').textContent='You · Live';$('rep-note').textContent='Live count is provisional until full analysis.';setReps(0);let lastInference=-Infinity;
 // At most one inference in flight; frames are skipped (never queued) while it runs.
 const loop=()=>{if(!state.tracking)return;if(state.pausedAt){liveHandle=requestAnimationFrame(loop);return;}const t=(performance.now()-state.recordStart)/1000;if(t>(state.config?.maxRecordingSeconds||180)){finishRecording();return;}$('video-time').textContent=clock(t);if(!tracker.busy&&t-lastInference>=tracker.minInterval&&motion.readyState>=2){lastInference=t;tracker.estimate(motion,t,{live:true}).then(r=>liveResult(r,t),error=>console.warn('Pose inference failed',error));}liveHandle=requestAnimationFrame(loop);};loop();}catch(error){hideBusy();$('stage-message').hidden=true;toast(error.message);}}
async function finishRecording(){if(!state.tracking)return;stopCoaching();state.tracking=false;cancelAnimationFrame(liveHandle);engine?.resetTracking('recording finished');$('finish').disabled=true;try{const blob=await new Promise(resolve=>{state.recorder.onstop=()=>resolve(new Blob(state.chunks,{type:state.recorder.mimeType}));state.recorder.stop();});state.stream.getTracks().forEach(t=>t.stop());state.stream=null;motion.srcObject=null;setMirrored(false);busy('Saving your set','Preparing the recording for your report.');const job=state.job,rows=state.rows.slice(),uploaded=await uploadFile(new File([blob],blob.type.includes('mp4')?'camera.mp4':'camera.webm',{type:blob.type}));if(job!==state.job){hideBusy();return;}state.asset=uploaded.asset;
  /* Poses tracked steadily during the set are as good as tracking the saved video, and already timed to it. Sparser ones can miss a repetition. */
  if(rows.length>=Math.max(5,uploaded.duration*5)&&rows.every((r,i)=>!i||r.time-rows[i-1].time<=.5)){try{busy('Building your report','Comparing the patient’s movement with the therapist reference and extracting the actual clips.');const s=await post('/api/process',{asset:state.asset,reference:false,reference_id:state.config.referenceId,consent:true,rows});if(job===state.job){workout.remember(s);hideBusy();showResults(s);}else hideBusy();return;}catch(error){if(job!==state.job){hideBusy();return;}console.warn('Tracking the saved video instead:',error.message);}}
  /* Too few live poses, or they did not cover the set: track the saved video itself. */
  await loadVideo(motion,uploaded.url);state.mode='upload';hideBusy();await analyseUpload({paced:false});}catch(error){hideBusy();toast(error.message);inputState('reference');}finally{$('finish').disabled=false;}}
function showResults(s){delete coachBanner.dataset.tone;state.mode='results';state.session=s;state.liveReps=repetitionSummary(s).counted;setReps(state.liveReps);state.rows=s.landmarks;page('results');const value=s.match_score?.value;$('score-value').textContent=value===null||value===undefined?'—':`${value}%`;$('score-fill').style.width=`${value||0}%`;$('result-duration').textContent=`${Math.round(s.duration)} sec`;$('result-reps').textContent=`${s.repetitions} ${s.repetitions===1?'rep':'reps'}`;$('result-coverage').textContent=`${Math.round(s.coverage)}%`;$('result-reviewed').textContent=`${Math.min(acceptedReps(s),s.target)} / ${s.target}`;const scores=new Map((s.match_score.per_repetition||[]).map(r=>[r.rep,r.value]));$('rep-bars').innerHTML=s.cycles.map(c=>`<button class="rep-bar" data-rep="${c.rep}" aria-label="Replay repetition ${c.rep}"><span>${scores.get(c.rep)??'—'}</span><i><b style="height:${scores.get(c.rep)||0}%"></b></i><span>${c.rep}</span></button>`).join('')||'<p class="subtle">No complete repetitions were visible.</p>';$('rep-bars').querySelectorAll('button').forEach(b=>b.onclick=()=>openReplay(s.cycles.find(c=>c.rep===+b.dataset.rep).start));const groups=new Map();for(const f of s.flags){if(!groups.has(f.kind))groups.set(f.kind,[]);groups.get(f.kind).push(f);}$('feedback').innerHTML=[...groups.entries()].slice(0,3).map(([kind,flags])=>`<article><h3>${esc({pace:'A different pace',range:'A smaller movement range',pattern:'A movement pattern to review',tracking:'Part of the recording was unclear',assessment:'The movement could not be fully assessed'}[kind]||'A moment to review')}</h3><p>${flags.length>1?`${flags.length} moments to review. `:''}${esc(flags[0].detail)}</p><p>${esc(flags[0].cue)}</p></article>`).join('')||'<article><h3>Your recording is ready</h3><p>No comparison differences exceeded the current thresholds. This does not establish clinical correctness.</p></article>';if(s.feedback)$('feedback').innerHTML+=`<article><h3>From your physiotherapist</h3><p>${esc(s.feedback)}</p></article>`;$('download-bundle').href=`/api/bundle/${s.id}`;loadHistory();}
async function openReplay(t=0){
 cleanup();page('work');inputState('replay');state.replay=state.session.landmarks;
 $('tracking-status').textContent='Recording replay';$('live-hint').textContent='Compare the same stage of the movement.';$('rep-note').textContent='The therapist replay follows the phase of your repetition.';$('live-reps').nextElementSibling.textContent=`/${state.session.target||5}`;
 const id=state.session.reference?.reference_session_id;
 if(id){const r=await api(`/api/session/${id}`);state.referenceRows=r.landmarks;state.referenceCycles=r.cycles;state.referenceLoadedId=r.id;}
 await loadVideo(motion,state.session.source);motion.loop=false;
 if(state.session.reference_source){await loadVideo(mini,state.session.reference_source);mini.pause();}
 await seek(motion,t);await playSafe(motion);setIcon($('play-pause'),'pause');paintReplay();
}
function evidenceMarkup(s){
 const a=s.motion_analysis;if(!a)return '';
 const number=(n,unit)=>n===null||n===undefined?'—':`${n.toFixed(1)}${unit}`;
 return `<div class="report-section" id="motion-evidence"><h2>Movement analysis</h2><p>Each complete repetition is compared with your therapist’s movement. Timing is measured separately from movement shape.</p><div class="evidence-stats"><div><strong>${number(a.median_duration,'s')}</strong><span>Median repetition</span></div><div><strong>${number(a.reference_duration,'s')}</strong><span>Therapist reference</span></div><div><strong>${number(a.tempo_variation_pct,'%')}</strong><span>Timing variation</span></div><div><strong>${number(a.excursion_variation_pct,'%')}</strong><span>Excursion variation</span></div></div><label for="evidence-rep">Inspect a repetition</label><select id="evidence-rep">${a.repetitions.map(r=>`<option value="${r.rep}">Repetition ${r.rep} · ${r.start.toFixed(1)}–${r.end.toFixed(1)}s</option>`).join('')}</select><div id="evidence-detail"></div><p class="evidence-limit">${esc(a.interpretation)}</p></div>`;
}
function evidenceChart(f){
 const all=[...f.observed_curve,...f.reference_curve],minimum=Math.min(...all),maximum=Math.max(...all),range=Math.max(maximum-minimum,2*f.comparison_tolerance,.001),low=(maximum+minimum-range)/2,high=low+range;
 const path=values=>values.map((v,i)=>`${i?'L':'M'}${(30+i/(values.length-1)*440).toFixed(1)},${(153-(v-low)/range*125).toFixed(1)}`).join(' ');
 return `<div class="feature-evidence"><h3>${esc(f.label)}</h3><div class="chart-legend"><span><i aria-hidden="true">━</i> Your movement</span><span><i aria-hidden="true">┄</i> Therapist reference curve</span></div><svg viewBox="0 0 500 185" role="img" aria-label="${esc(f.label)} across a complete repetition"><path d="M30 25V154H470" fill="none" stroke="#dce5e1"/><path d="${path(f.reference_curve)}" fill="none" stroke="#e1e6f2" stroke-width="2.2" stroke-dasharray="6 4"/><path d="${path(f.observed_curve)}" fill="none" stroke="#a6fac5" stroke-width="2.7"/><text x="30" y="177">Start</text><text x="420" y="177">Return</text></svg><p class="chart-scale">Vertical scale: ${low.toFixed(2)} to ${high.toFixed(2)} ${esc(f.unit)}. Horizontal axis: repetition progress.</p><p>Mean aligned difference: <b>${f.mean_difference.toFixed(3)} ${esc(f.unit)}</b>. Outside the comparison tolerance in <b>${f.outside_tolerance_pct.toFixed(0)}%</b> of aligned observations.</p></div>`;
}
function bindEvidence(s){const select=$('evidence-rep');if(!select)return;select.onchange=()=>{
 const r=s.motion_analysis.repetitions.find(r=>r.rep===+select.value);if(!r){$('evidence-detail').innerHTML='<p>No complete repetitions were assessable.</p>';return;}
 $('evidence-detail').innerHTML=`<div class="phase-times"><span>To movement peak <b>${r.outward_seconds.toFixed(2)}s</b></span><span>Return <b>${r.return_seconds.toFixed(2)}s</b></span></div><button id="evidence-replay" class="secondary">${icon('play')}Replay repetition ${r.rep}</button>${r.features.map(f=>f.available?evidenceChart(f):`<p>${esc(f.label)}: ${esc(f.reason)}</p>`).join('')||`<p>${esc(s.motion_analysis.reason)}</p>`}`;
 $('evidence-replay').onclick=safe(()=>openReplay(r.start));
 };select.onchange();}
const FEATURE_LABELS={knee_angle:'Left knee angle (2D, deg)',hip_angle:'Left hip angle (2D, deg)',torso_lean:'Trunk lean (2D, deg)',knee_offset:'Left knee offset (leg lengths)',hip_height:'Hip height (torso lengths, per frame)'};
function vitposeMarkup(check){
 if(!check)return '';const fmt=v=>v===null||v===undefined?'—':Math.abs(v)>=10?v.toFixed(1):v.toFixed(3);
 const rows=Object.entries(check.summary).map(([k,v])=>`<tr><td>${esc(FEATURE_LABELS[k]||k)}</td><td>${v.compared}</td><td>${fmt(v.median_abs_difference)}</td></tr>`).join('');
 const frames=check.checkpoints.map(c=>`<tr><td>${c.rep??'—'} · ${esc(c.phase)}</td><td>${c.time.toFixed(2)}s</td><td>${fmt(c.browser.features.knee_offset)} / ${fmt(c.vitpose.features.knee_offset)}</td><td>${fmt(c.browser.features.torso_lean)} / ${fmt(c.vitpose.features.torso_lean)}</td></tr>`).join('');
 return `<p>${check.checkpoints.length} frames checked with ${esc(check.repository)} on the person boxes chosen by the browser tracker (${esc(MODELS[check.browser_model]?.label||'browser model')}).</p><div class="table-wrap"><table><thead><tr><th>Measurement</th><th>Frames</th><th>Median |difference|</th></tr></thead><tbody>${rows}</tbody></table></div><details><summary>Per-frame values (browser / ViTPose)</summary><div class="table-wrap"><table><thead><tr><th>Rep · phase</th><th>Time</th><th>Knee offset</th><th>Trunk lean</th></tr></thead><tbody>${frames}</tbody></table></div></details><p>${esc(check.note)}</p>`;
}
function poseModelsMarkup(s){
 const legacy=s.pose_engine==='mediapipe-pose-landmarker-full';
 const vit=state.config?.pose?.vitpose,check=s.model_checks?.vitpose;
 const unavailable=(s.unavailable_measurements||[]).map(m=>`<li><b>${esc(m.label)}</b>: ${esc(m.reason)}</li>`).join('');
 const action=legacy?'<p>This session was recorded with the previous MediaPipe engine; a ViTPose check needs a session tracked with the current engine.</p>'
  :vit?.available?`<label class="consent"><input id="vitpose-consent" type="checkbox">Re-analyse selected frames of this already uploaded recording on the Wathba server. No third-party service is used.</label><button id="vitpose-run" class="secondary">${check?'Run the ViTPose check again':'Run ViTPose check'}</button>`
  :`<p>ViTPose check unavailable on this server: ${esc(vit?.reason||'not configured')}</p>`;
 return `<div class="report-section" id="pose-models"><h2>Pose models</h2><p>${esc(s.model)}. Joints are 2D image-plane estimates (17 COCO keypoints); angles change with camera position.</p>${unavailable?`<p>Not measured with these models:</p><ul class="unavailable-list">${unavailable}</ul>`:''}<h3>ViTPose frame check</h3><div id="vitpose-result">${vitposeMarkup(check)}</div>${action}</div>`;
}
function bindPoseModels(s){
 const run=$('vitpose-run');if(!run)return;
 run.onclick=safe(async()=>{
  if(!$('vitpose-consent').checked)throw Error('Confirm that this recording may be re-analysed on the Wathba server.');
  run.disabled=true;busy('Checking selected frames with ViTPose','Running on the Wathba server with the tracked person boxes. The first run downloads the model.');
  try{const check=await post(`/api/session/${s.id}/vitpose-check`,{consent:true});s.model_checks={...(s.model_checks||{}),vitpose:check};$('vitpose-result').innerHTML=vitposeMarkup(check);}finally{hideBusy();run.disabled=false;}
 });
}
// ------------------------------------------------------------- post-exercise check-in
const LOCATIONS=[['knee','Knee'],['hip','Hip'],['back','Lower back'],['ankle','Ankle'],['other','Other']];
const DIFFICULTY=[['easy','Easy'],['moderate','Moderate'],['hard','Hard']];
const chip=(name,value,label,checked,type='radio')=>`<label class="chip"><input type="${type}" name="${name}" value="${value}" ${checked?'checked':''}><span>${label}</span></label>`;
const yesNo=(name,value)=>`<div class="chips">${chip(name,'no','No',value===false)}${chip(name,'yes','Yes',value===true)}</div>`;
function checkInForm(c={}){
 return `<form class="check-in-form">
 <fieldset><legend>Did you feel pain during the exercise?</legend>${yesNo('pain_during',c.pain_during)}</fieldset>
 <fieldset><legend>How much pain do you feel now, after the exercise?</legend><div class="chips pain-scale">${Array.from({length:11},(_,n)=>chip('pain_after',n,n,c.pain_after===n)).join('')}</div><small>0 = no pain · 10 = worst pain</small></fieldset>
 <fieldset><legend>Where did you feel it?</legend><div class="chips">${LOCATIONS.map(([v,l])=>chip('pain_locations',v,l,(c.pain_locations||[]).includes(v),'checkbox')).join('')}</div></fieldset>
 <fieldset><legend>How hard was the exercise?</legend><div class="chips">${DIFFICULTY.map(([v,l])=>chip('difficulty',v,l,c.difficulty===v)).join('')}</div></fieldset>
 <fieldset><legend>Did your knee feel unstable or give way?</legend>${yesNo('knee_unstable',c.knee_unstable)}</fieldset>
 <fieldset><legend>Do you notice new swelling?</legend>${yesNo('swelling',c.swelling)}</fieldset>
 <label class="notes-label"><span>Anything else for your physiotherapist? (optional)</span><textarea name="notes" maxlength="1000" rows="2">${esc(c.notes||'')}</textarea></label>
 <button class="primary" type="submit">Save answers</button></form>`;
}
function checkInSummary(c){
 const yn=v=>v===null||v===undefined?'Not answered':v?'Yes':'No',label=(list,v)=>list.find(([k])=>k===v)?.[1];
 const rows=[['Pain during',yn(c.pain_during)],['Pain after (0–10)',c.pain_after??'Not answered'],['Where',(c.pain_locations||[]).map(v=>label(LOCATIONS,v)).join(' · ')||'Not specified'],['Difficulty',label(DIFFICULTY,c.difficulty)||'Not answered'],['Knee unstable',yn(c.knee_unstable)],['New swelling',yn(c.swelling)]];
 const alert=c.attention?.length?'<p class="check-in-alert" role="alert"><b>Needs attention</b><span>Your answers mention pain, instability or swelling. Stop if it gets worse and contact your physiotherapist before your next session. This is not a diagnosis.</span></p>':'';
 return `${c.scope==='workout'?'<p class="subtle">Answers cover all exercises in this session.</p>':''}${alert}<dl class="check-in-answers">${rows.map(([k,v])=>`<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>${c.notes?`<p class="check-in-notes"><b>Notes</b><span data-no-i18n>${esc(c.notes)}</span></p>`:''}<button type="button" class="text-button" data-check-in-edit>Edit answers</button>`;
}
function renderCheckIn(host,s,editing=!s.check_in,options={}){
 if(!host)return;
 const formHtml=checkInForm(s.check_in||{}).replaceAll('during the exercise','during any exercise in this session').replaceAll('after the exercise','after the whole session').replaceAll('How hard was the exercise?','How hard was the whole session?');
 host.innerHTML=editing?formHtml:checkInSummary(s.check_in);
 host.querySelector('[data-check-in-edit]')?.addEventListener('click',()=>renderCheckIn(host,s,true,options));
 const form=host.querySelector('form');
 if(form)form.onsubmit=safe(async e=>{
  e.preventDefault();const f=new FormData(form),yn=n=>f.get(n)==='yes'?true:f.get(n)==='no'?false:null;
  const answers={pain_during:yn('pain_during'),pain_after:f.get('pain_after')===null?null:Number(f.get('pain_after')),pain_locations:f.getAll('pain_locations'),difficulty:f.get('difficulty')||null,knee_unstable:yn('knee_unstable'),swelling:yn('swelling'),notes:String(f.get('notes')||'').trim()};
  const button=form.querySelector('button[type=submit]');button.disabled=true;
  try{const updated=await post('/api/workout/check-in',{...answers,session_ids:options.sessionIds});Object.assign(s,{check_in:updated.check_in});if(options.sessionIds.includes(state.session?.id))state.session.check_in=updated.check_in;renderCheckIn(host,s,false,options);options.onSaved?.();toast('Answers saved. Your physiotherapist will see them in your report.');}
  finally{button.disabled=false;}
 });
}
function showWorkoutEvaluation(session=state.session,review=false){
 if(!session)return;
 cleanup();
 let screen=$('workout-evaluation');
 if(!screen){
  screen=document.createElement('section');screen.id='workout-evaluation';screen.className='page report-page';screen.hidden=true;
  screen.innerHTML='<div class="screen-heading"><button id="evaluation-back" class="secondary" type="button">Back</button><h1>How did you feel?</h1></div><p class="subtle">Evaluate pain and effort across all exercises you just completed.</p><div id="workout-evaluation-form" class="glass check-in-card"></div><button id="evaluation-finish" class="primary" type="button" hidden>Back to Home</button>';
  document.querySelector('main').append(screen);
 }
 const sessionIds=review?(session.check_in?.session_ids||[session.id]):workout.sessions(session);
 // A previous workout's answers must not prefill a newly completed workout.
 const sameAnswers=session.check_in?.scope==='workout'&&sessionIds.every(id=>session.check_in.session_ids?.includes(id));
 const subject={...session,check_in:sameAnswers?session.check_in:null};
 $('evaluation-finish').hidden=!sameAnswers;
 $('evaluation-finish').onclick=()=>{cleanup();page('home');};
 $('evaluation-back').onclick=()=>page('summary');
 renderCheckIn($('workout-evaluation-form'),subject,!sameAnswers,{sessionIds,onSaved:()=>{workout.complete(sessionIds);$('evaluation-finish').hidden=false;}});
 page('workout-evaluation');
}
// --------------------------------------------------------------- AI coach (Qwen3)
const aiSummaryHtml=r=>r.fixed?`<p class="ai-text" data-no-i18n dir="auto">${esc(r.text)}</p><small class="ai-meta">Written by the app from your measured results, not by the AI model.</small>`:r.checked?`<p class="ai-text" data-no-i18n dir="auto">${esc(r.text)}</p><small class="ai-meta">${esc(r.stats?.repo||'Qwen3')} · ${r.stats?.seconds??'—'} s</small>`
 :`<p class="subtle">The model's summary did not pass the automatic checks, so it is not shown.</p>`;
const aiAnswerHtml=q=>`<div class="ai-q"><b data-no-i18n dir="auto">${esc(q.question)}</b><p data-no-i18n dir="auto">${esc(q.text)}</p></div>`;
function aiSection(s){
 const ai=state.config?.ai?.text,lang=currentLang(),sum=s.ai?.summary?.[lang],qs=(s.ai?.questions||[]).filter(q=>q.lang===lang).slice(-6);
 if(!ai?.available)return `<div class="report-section ai-card"><h2>AI coach</h2><p class="subtle">The AI coach is not available on this server.</p><p class="subtle" data-no-i18n>${esc(ai?.reason||'')}</p></div>`;
 return `<div class="report-section ai-card" id="ai-card"><h2>AI coach</h2>
 <p class="subtle">Written by a Qwen3 model running on the Wathba server, using only your measured results and answers. Every reply is checked automatically. Not medical advice.</p>
 <label class="consent"><input id="ai-consent" type="checkbox">Allow the Qwen3 model on the Wathba server to process this session. Nothing is sent to other services.</label>
 <div id="ai-summary">${sum?aiSummaryHtml(sum):''}</div>
 <button id="ai-summary-run" class="secondary" type="button">${sum?'Write the summary again':'Write my summary'}</button>
 <h3>Ask about this session</h3>
 <div id="ai-thread">${qs.map(aiAnswerHtml).join('')}</div>
 <form id="ai-ask" class="ai-ask"><input name="question" maxlength="500" autocomplete="off" placeholder="For example: how many repetitions did I do?" aria-label="Your question"><button class="primary" type="submit">Ask</button></form></div>`;
}
function visionSection(s){
 const vision=state.config?.ai?.vision,review=s.ai?.vision;
 if(!vision?.available)return '';
 const body=review?(review.checked?`<p class="ai-text" data-no-i18n dir="auto">${esc(review.text)}</p><small class="ai-meta">${esc(review.stats?.repo||'Qwen3-VL')} · ${review.frame_times.length} frames</small>`:`<p class="subtle">The description did not pass the automatic checks, so it is not shown.</p>`):'';
 return `<div class="report-section"><h2>Vision model review</h2><p>Experimental: a Qwen3-VL model describes the start and bottom of your first repetitions. It does not change your score.</p><div id="ai-vision">${body}</div><button id="ai-vision-run" class="secondary" type="button">Describe the frames</button></div>`;
}
function bindAi(s){
 const consent=()=>{if(!$('ai-consent')?.checked)throw Error('Confirm that this session may be processed by the Qwen3 model on the Wathba server.');return true;};
 const store=(kind,result)=>{s.ai??={};if(kind==='summary')(s.ai.summary??={})[result.lang]=result;else if(kind==='question')s.ai.questions=[...(s.ai.questions||[]),result];else s.ai.vision=result;};
 if($('ai-summary-run'))$('ai-summary-run').onclick=safe(async()=>{consent();busy('Writing your summary','The Qwen3 model is reading your session on the Wathba server. The first run loads the model.');
  try{const r=await post(`/api/session/${s.id}/ai/summary`,{consent:true,lang:currentLang()});store('summary',r);$('ai-summary').innerHTML=aiSummaryHtml(r);$('ai-summary-run').textContent='Write the summary again';}finally{hideBusy();}});
 if($('ai-ask'))$('ai-ask').onsubmit=safe(async e=>{e.preventDefault();consent();const input=$('ai-ask').elements.question,question=input.value.trim();if(!question)throw Error('Type a question first.');
  const button=$('ai-ask').querySelector('button');button.disabled=true;$('ai-thread').insertAdjacentHTML('beforeend','<p class="subtle ai-wait">Thinking…</p>');
  try{const r=await post(`/api/session/${s.id}/ai/ask`,{consent:true,lang:currentLang(),question});store('question',r);input.value='';$('ai-thread').insertAdjacentHTML('beforeend',aiAnswerHtml(r));}
  finally{button.disabled=false;$('ai-thread').querySelector('.ai-wait')?.remove();}});
 if($('ai-vision-run'))$('ai-vision-run').onclick=safe(async()=>{
  if(!$('ai-consent')?.checked)throw Error('Confirm that this session may be processed by the Qwen3 model on the Wathba server.');
  busy('Describing the frames','The Qwen3-VL model is looking at your repetitions on the Wathba server. The first run loads the model.');
  try{const r=await post(`/api/session/${s.id}/ai/vision`,{consent:true,lang:currentLang()});store('vision',r);$('ai-vision').innerHTML=r.checked?`<p class="ai-text" data-no-i18n dir="auto">${esc(r.text)}</p><small class="ai-meta">${esc(r.stats?.repo||'Qwen3-VL')} · ${r.frame_times.length} frames</small>`:'<p class="subtle">The description did not pass the automatic checks, so it is not shown.</p>';}finally{hideBusy();}});
}
// ---------------------------------------------------------------------- report
function showReport(){const s=state.session;page('report');
 const value=s.match_score?.value,when=new Intl.DateTimeFormat(currentLang()==='ar'?'ar':'en',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Qatar'}).format(new Date(s.created_at));
 const stat=(v,l)=>`<div><strong>${v}</strong><span>${l}</span></div>`;
 const reps=s.cycles.map(c=>`<tr><td>${c.rep}</td><td>${c.start.toFixed(1)}–${c.end.toFixed(1)}s</td><td>${c.duration.toFixed(2)}s</td><td>${c.excursion.toFixed(2)}</td><td>${s.match_score.per_repetition?.find(r=>r.rep===c.rep)?.value??'—'}%</td></tr>`).join('');
 $('report-body').innerHTML=`<div class="report-section report-summary"><h2>Squat · left leg</h2><p class="subtle" data-no-i18n>${esc(when)}</p><div class="report-stats">${stat(s.repetitions,'Repetitions')}${stat(`${Math.round(s.duration)} sec`,'Duration')}${stat(`${Math.round(s.coverage)}%`,'Tracking')}${stat(value===null||value===undefined?'—':`${value}%`,'Reference match')}</div></div>
 <div class="report-section check-in-card" id="check-in-report"></div>
 ${aiSection(s)}
 <div class="report-section"><h2>From your physiotherapist</h2><p>${esc(s.feedback||'Awaiting physiotherapist review.')}</p></div>
 <div class="report-section"><h2>Moments to review</h2><select id="clip-choice" aria-label="Choose a review clip">${s.flags.map((f,i)=>`<option value="${i}">${f.start.toFixed(1)}–${f.end.toFixed(1)}s · ${esc(f.title)}</option>`).join('')}</select><div id="clip-detail"></div></div>
 <details class="report-section technical-details"><summary>Technical details</summary>
  <h3>Annotated recording</h3><video controls playsinline src="${esc(s.annotated)}"></video>
  ${evidenceMarkup(s)}
  <div class="report-section"><h2>Repetition detail</h2><div class="table-wrap"><table><thead><tr><th>Rep</th><th>Interval</th><th>Duration</th><th>Excursion*</th><th>Match</th></tr></thead><tbody>${reps}</tbody></table></div><p>*Frontal pelvic movement relative to torso length, measured in the 2D image plane; not calibrated clinical knee range.</p></div>
  ${visionSection(s)}
  ${poseModelsMarkup(s)}
  <div class="report-section"><h2>How to interpret this</h2><p>${esc(s.match_score.reason||'No comparison score was available.')}</p>${s.limitations.map(l=>`<p>${esc(l)}</p>`).join('')}</div>
 </details>`;
 const checkInHost=$('check-in-report');checkInHost.innerHTML='<h2>Session evaluation</h2>'+(s.check_in?checkInSummary(s.check_in):'<p class="subtle">Complete all exercises, then select Finish Session to evaluate the whole session.</p>');checkInHost.querySelector('[data-check-in-edit]')?.addEventListener('click',()=>showWorkoutEvaluation(s,true));
 const select=$('clip-choice');if(s.flags.length){select.onchange=()=>{const f=s.flags[+select.value];$('clip-detail').innerHTML=`<video controls playsinline src="${esc(f.clip)}"></video><p>${esc(f.detail)}</p><p>${esc(f.cue)}</p>`;};select.onchange();}else{select.hidden=true;$('clip-detail').innerHTML='<p>No moments were flagged.</p>';}
 $('download-report').href=s.report;bindEvidence(s);bindPoseModels(s);bindAi(s);}
// Re-render date-formatted screens when the language changes.
window.addEventListener('wathba:lang',()=>{if(!$('report').hidden&&state.session)showReport();});
async function loadHistory(){const history=await api('/api/history');$('history').innerHTML=history.slice(0,3).map((s,i)=>`<button data-session="${s.id}">Previous set ${i+1} · ${s.repetitions} reps · ${s.score??'—'}% reference match</button>`).join('');$('history').querySelectorAll('button').forEach(b=>b.onclick=async()=>showResults(await api(`/api/session/${b.dataset.session}`)));}
function safe(fn){return async(...args)=>{try{await fn(...args);}catch(error){hideBusy();if(error.name!=='AbortError')toast(error.message);}};}
$('start-workout').onclick=safe(startWorkout);$('back-home').onclick=()=>{cleanup();page('home');};$('use-camera').onclick=safe(chooseCamera);sampleButton.onclick=safe(chooseSample);$('upload-video').onclick=()=>{$('file-input').click();};$('file-input').onchange=safe(e=>chooseUpload(e.target.files[0]));$('analyse').onclick=safe(analyseUpload);$('record').onclick=safe(startRecording);$('finish').onclick=safe(finishRecording);$('cancel-analysis').onclick=()=>{state.job++;engine?.resetTracking('cancelled');inputState('upload');toast('Analysis cancelled. You can start again.');};$('toggle-view').onclick=()=>{const skeleton=$('stage').classList.toggle('skeleton-only');$('toggle-view').setAttribute('aria-label',skeleton?'Switch to video view':'Switch to skeleton view');setIcon($('toggle-view'),skeleton?'camera':'accessibility');};$('score-info').onclick=()=>{$('score-explanation').hidden=!$('score-explanation').hidden;};$('open-replay').onclick=safe(()=>openReplay());$('open-report').onclick=showReport;$('report-back').onclick=() =>showResults(state.session);$('back-results').onclick=()=>showResults(state.session);$('done').onclick=()=>showWorkoutEvaluation();$('results-home').onclick=()=>{cleanup();page('home');};$('play-pause').onclick=safe(async()=>{if(motion.paused){await playSafe(motion);setIcon($('play-pause'),'pause');}else{motion.pause();setIcon($('play-pause'),'play');}});$('seek').oninput=safe(async()=>seek(motion,+$('seek').value/1000*motion.duration));$('previous-rep').onclick=safe(()=>{const c=[...state.session.cycles].reverse().find(c=>c.start<motion.currentTime-.8)||state.session.cycles[0];if(c)return seek(motion,c.start);});$('next-rep').onclick=safe(()=>{const c=state.session.cycles.find(c=>c.start>motion.currentTime+.4);if(c)return seek(motion,c.start);});$('refresh-feedback').onclick=safe(async()=>{state.session=await api(`/api/session/${state.session.id}`);showReport();toast('Physiotherapist feedback refreshed.');});

$('prepare-reference').onclick=safe(async()=>{
 const file=$('reference-file').files[0];
 if(!file)throw Error('Choose a therapist demonstration first.');
 if(!$('reference-consent').checked)throw Error('Confirm permission to use the therapist demonstration.');
 cleanup();const job=state.job;busy('Preparing therapist reference','Reading the uploaded demonstration.');
 try{
  const uploaded=await uploadFile(file);const v=document.createElement('video');v.muted=true;v.playsInline=true;
  await loadVideo(v,uploaded.url);const rows=await extractVideo(v,job,p=>busy('Preparing therapist reference','Tracking the demonstration in this browser.',p));
  const r=await post('/api/process',{asset:uploaded.asset,reference:true,consent:true,rows});
  state.config=await api('/api/config');state.referenceRows=rows;
  $('reference-ready').textContent=`Reference ready: ${r.model.training_cycles} complete demonstration repetitions. The patient session will now use this recording.`;
 }finally{hideBusy();}
});
$('stage-pause').onclick=safe(async()=>{
 if(state.mode==='recording'&&state.recorder){
  if(state.recorder.state==='recording'){state.recorder.pause();stopCoaching();resetLive();state.pausedAt=performance.now();setIcon($('stage-pause'),'play');$('stage-pause').setAttribute('aria-label','Resume session');$('tracking-status').textContent='Session paused';}
  else if(state.recorder.state==='paused'){state.recordStart+=performance.now()-state.pausedAt;state.pausedAt=null;engine?.resetTracking('resumed');startVoice();if(audioCoach.enabled)await audioCoach.unlock();state.recorder.resume();setIcon($('stage-pause'),'pause');$('stage-pause').setAttribute('aria-label','Pause session');$('tracking-status').textContent='You · Live';}
 }else if(motion.paused)await playSafe(motion);else motion.pause();
});
for(const event of ['play','pause'])motion.addEventListener(event,()=>{setIcon($('stage-pause'),motion.paused?'play':'pause');setIcon($('play-pause'),motion.paused?'play':'pause');$('stage-pause').setAttribute('aria-label',motion.paused?'Play video':'Pause video');});
// Release the camera and the model sessions/worker when the page goes away.
window.addEventListener('pagehide',()=>{cleanup();const e=engine;engine=null;e?.dispose();});
try{state.config=await api('/api/config');document.documentElement.style.setProperty('--poster',state.config.poster?`url("${state.config.poster}")`:'none');$('hero-image').src=$('exercise-thumb').src=state.config.poster||'';$('start-workout').disabled=false;
 // Load and warm up the pose models in the background so starting an exercise does not wait for them.
 state.referencePreload=preloadReference();(window.requestIdleCallback||(f=>setTimeout(f,1200)))(()=>ensureEngine().catch(error=>console.warn('Pose model preload failed; it will be retried when needed.',error.message)),{timeout:3000});
 await loadHistory();const params=new URLSearchParams(location.search);if(params.has('reference'))page('reference-setup');else if(params.has('session'))showResults(await api(`/api/session/${encodeURIComponent(params.get('session'))}`));}catch(error){toast(error.message);}
// Expose read-only diagnostics for verifying the actual browser models and source roles.
window.wathbaDiagnostics=()=>({mode:state.mode,referenceId:state.config?.referenceId,referenceFrames:state.referenceRows.length,patientFrames:state.rows.length,liveRepetitions:state.liveReps,session:state.session?.id,model:state.session?.model,referenceSynthetic:state.session?.reference?.synthetic,pose:engine?.status()??null});

$('guide-pause').onclick=safe(async()=>{if(mini.paused)await playSafe(mini);else mini.pause();});
for(const event of ['play','pause'])mini.addEventListener(event,()=>{setIcon($('guide-pause'),mini.paused?'play':'pause');$('guide-pause').setAttribute('aria-label',mini.paused?'Play therapist demonstration':'Pause therapist demonstration');});

export {state,page,startWorkout,showResults,openReplay,showReport,api,post,toast,cleanup,showWorkoutEvaluation};
