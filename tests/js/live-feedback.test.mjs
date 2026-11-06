import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {joint,CONFIG,makePose} from '../../web/pose/schema.js';
import {evaluateLive,measurements} from '../../web/motion-coach.js';
import {RepCounter,AlertGate} from '../../web/rep-counter.js';

const app=fs.readFileSync(new URL('../../web/app.js',import.meta.url),'utf8');
const logic=app.slice(app.indexOf('function hipHeight(pose){'),app.indexOf('async function startRecording()'));
function harness(reference,rows=[],cycles=[]){
 const counter=new RepCounter(),gate=new AlertGate(),alerts=[],elements=new Map();let time=0;
 const get=id=>{if(!elements.has(id))elements.set(id,{style:{}});return elements.get(id);};
 const state={tracking:true,mode:'recording',config:{referenceModel:reference,target:5},referenceRows:rows,referenceCycles:cycles,rows:[],lastSample:-1};
 const context=vm.createContext({state,repCounter:counter,joint,REQUIRED:CONFIG.measurementRequirements.hip_height,
  evaluateLive,measurements,countStatus:{},$:get,rowFrom:(r,t)=>({time:t}),draw(){},setReps(){},currentLang:()=> 'en',
  performance:{now:()=>time*1000},audioCoach:{update(issue,t,immediate){if(gate.update(issue,t,immediate))alerts.push(issue);}},
  resetLive(){counter.reset();state.liveTorsoScale=null;state.floorPosition=null;}
 });
 vm.runInContext(logic,context);
 vm.runInContext(app.slice(app.indexOf('function setReps(n){'),app.indexOf('async function extractVideo(')),context);
 return {counter,state,alerts,context,get,feed(result,t,finishing=false){time=t;context.liveResult(result,t,finishing);}};
}
test('persistent lost tracking reaches the audible alert gate instead of resetting it each frame',()=>{
 const h=harness({keypoint_model:'movenet-singlepose-lightning',templates:{hip_height:{}},primary_feature:'hip_height'});
 for(let t=0;t<2;t+=.1)h.feed({status:'no-pose'},t);
 assert.deepEqual(h.alerts,['tracking']);assert.equal(h.counter.accepted,0);
});
test('analysis of an upload also drives feedback without enabling live camera recording',()=>{
 const h=harness({keypoint_model:'movenet-singlepose-lightning',templates:{hip_height:{}},primary_feature:'hip_height'});
 h.state.tracking=false;h.state.mode='analysing';
 for(let t=0;t<2;t+=.1)h.feed({status:'no-pose'},t);
 assert.deepEqual(h.alerts,['tracking']);assert.equal(h.state.rows.length,0);
});
test('stored therapist reference passes the complete live measurement and counting pipeline',{
 skip:!process.env.WATHBA_TEST_REFERENCE_DIR&&'WATHBA_TEST_REFERENCE_DIR not set'
},()=>{
 const directory=process.env.WATHBA_TEST_REFERENCE_DIR;
 const model=JSON.parse(fs.readFileSync(path.join(directory,'motion-model.json'),'utf8'));
 const session=JSON.parse(fs.readFileSync(path.join(directory,'report.json'),'utf8'));
 const rows=session.browser_landmarks,h=harness(model,rows,session.cycles);
 // Recover the original image aspect ratio from the matching named/pixel rows.
 const pixel=session.samples.find(s=>s.points&&s.time===rows.find(r=>r.keypoints)?.time);
 const row=rows.find(r=>r.keypoints),index=CONFIG.joints.indexOf('left_hip');
 const width=pixel.points[index][0]/row.keypoints.left_hip.x,height=pixel.points[index][1]/row.keypoints.left_hip.y;
 for(const r of rows){const pose=r.model?makePose({...r,width,height,timestamp:r.time}):null;
  h.feed({status:pose?'ok':'no-pose',pose},r.time);
 }
 assert.equal(h.counter.observed,session.cycles.length);
 assert.equal(h.counter.accepted,session.cycles.length);
});

for(const directory of (process.env.WATHBA_TEST_PATIENT_DIRS||'').split(path.delimiter).filter(Boolean)){
 test('patient repetitions reach the displayed target counter and agree with stored review: '+path.basename(directory),()=>{
  const session=JSON.parse(fs.readFileSync(path.join(directory,'report.json'),'utf8'));
  const refDirectory=path.join(path.dirname(directory),session.reference_model.reference_session_id);
  const model=JSON.parse(fs.readFileSync(path.join(refDirectory,'motion-model.json'),'utf8'));
  const ref=JSON.parse(fs.readFileSync(path.join(refDirectory,'report.json'),'utf8'));
  const rows=session.browser_landmarks,h=harness(model,ref.browser_landmarks,ref.cycles);
  const row=rows.find(r=>r.keypoints),pixel=session.samples.find(s=>s.points&&s.time===row.time);
  const width=pixel.points[11][0]/row.keypoints.left_hip.x,height=pixel.points[11][1]/row.keypoints.left_hip.y;
  let last;
  for(const r of rows){const pose=r.model?makePose({...r,width,height,timestamp:r.time}):null;
   last={status:pose?'ok':'no-pose',pose};h.feed(last,r.time);
  }
  h.feed(last,rows.at(-1).time,true);
  const expected=session.cycles.filter(c=>!c.findings.length).length;
  assert.ok(expected>0,'fixture includes a repetition accepted by the final comparison');
  assert.equal(h.counter.observed,session.repetitions);
  assert.equal(h.counter.accepted,expected);
  assert.ok(h.counter.counted>=h.counter.accepted);
  assert.equal(h.get('live-reps').textContent,Math.min(5,h.counter.counted));
 });
}
