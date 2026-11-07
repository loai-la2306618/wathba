import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('../../web/app.js',import.meta.url),'utf8');
const analyse=source.slice(source.indexOf('const VIEWING_STEP_MS'),source.indexOf('/** Frontal pelvic descent'));
for(const fails of [false,true])test(`99% analysis progress never changes the rep count (${fails?'failure':'success'})`,async()=>{
 const elements=new Map();
 const get=id=>{if(!elements.has(id))elements.set(id,{textContent:'',style:{},nextElementSibling:{textContent:'/5'}});return elements.get(id);};
 const state={job:0,liveReps:2,config:{target:5},asset:'test'};
 let notified=false,session=null;
 const context=vm.createContext({state,$:get,motion:{},clock:String,paintHandle:0,cancelAnimationFrame(){},inputState(){},startVoice(){},stopCoaching(){},workout:{remember(){}},audioCoach:{enabled:true,async unlock(){return true;},stop(){}},
  setReps(n){get('live-reps').textContent=n;},busy(){},hideBusy(){},toast(){notified=true;},
  async extractVideo(video,job,progress){progress(.99,26);return [];},
  async post(){if(fails)throw Error('processing failed');return {accepted_repetitions:2};},
  showResults(s){session=s;}
 });
 vm.runInContext(analyse,context);await context.analyseUpload();
 assert.equal(get('live-reps').textContent,2);
 assert.equal(get('live-reps').nextElementSibling.textContent,'/5');
 assert.match(get('tracking-status').textContent,/99%/);
 assert.equal(notified,fails);assert.equal(Boolean(session),!fails);
});
