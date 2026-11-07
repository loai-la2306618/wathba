import test from 'node:test';
import assert from 'node:assert/strict';
import {RepCounter,AlertGate,compareRepetition,countsTowardTarget} from '../../web/rep-counter.js';
import {AudioCoach} from '../../web/audio-coach.js';

// Segmented reference duration excludes the standing margins around the 2.5s motion.
const reference={duration_median:2,duration_mad:.1,templates:{
 hip_height:{excursion_median:.5,excursion_mad:.01,tolerance:.12},knee_offset:{},torso_lean:{}
}};
const green={leftKnee:{status:'green'},trunk:{status:'green'}};

test('full repetition comparison accepts the reference and rejects sustained alignment differences',()=>{
 const curve=Array.from({length:61},(_,i)=>-.5*(1-Math.cos(2*Math.PI*i/60))/2);
 const model={primary_feature:'hip_height',duration_median:2,templates:{
  hip_height:{median:curve,spread:curve.map(()=>0),tolerance:.12,excursion_median:.5,excursion_mad:0},
  knee_offset:{median:curve.map(()=>0),spread:curve.map(()=>0),tolerance:.08,excursion_median:0,excursion_mad:0}
 }};
 const samples=curve.map((v,i)=>({time:i/30,height:1+v,features:{knee_offset:0}}));
 assert.deepEqual(compareRepetition(samples,model),{assessable:true,issue:null,score:100});
 const different=compareRepetition(samples.map(s=>({...s,features:{knee_offset:.4}})),model);
 assert.equal(different.issue,'alignment');assert.ok(different.score>=60);
 assert.deepEqual(compareRepetition(samples.map(s=>({...s,features:{}})),model),{assessable:false});
});
test('60 percent is inclusive and remains distinct from a strictly correct repetition',()=>{
 for(const score of [60,61,100])assert.equal(countsTowardTarget(score),true);
 for(const score of [59,59.9,null,undefined,NaN])assert.equal(countsTowardTarget(score),false);
});
test('an imperfect assessable repetition can advance progress without becoming correct',()=>{
 const wave=Array.from({length:61},(_,i)=>-.5*(1-Math.cos(2*Math.PI*i/60))/2);
 const model={primary_feature:'hip_height',duration_median:2,duration_mad:.1,templates:{
  hip_height:{median:wave,spread:wave.map(()=>0),tolerance:.12,excursion_median:.5,excursion_mad:0},
  knee_offset:{median:wave.map(()=>0),spread:wave.map(()=>0),tolerance:.08,excursion_median:0,excursion_mad:0}
 }};
 const c=new RepCounter();let t=0;
 const feed=height=>c.update({time:t+=.1,height,features:{knee_offset:.1},parts:{leftKnee:{status:'yellow'}},reference:model});
 for(let i=0;i<12;i++)feed(1);
 for(let i=0;i<=25;i++)feed(1-.5*(1-Math.cos(2*Math.PI*i/25))/2);
 for(let i=0;i<10;i++)feed(1);
 assert.equal(c.observed,1);assert.equal(c.counted,1);assert.equal(c.accepted,0);
});
function drive(counter,{amplitude=.5,parts=green,gap=false,longGap=false,partial=false}={}){
 let time=0,result;
 const feed=(height,valid=true)=>{result=counter.update({time:time+=.1,height,valid,parts,reference});};
 for(let i=0;i<12;i++)feed(1);
 for(let i=0;i<=25;i++){
  feed(1-amplitude*(1-Math.cos(2*Math.PI*i/25))/2,!((gap&&i===12)||(longGap&&i>=9&&i<=17)));
  if(partial&&i===12)return result;
 }
 for(let i=0;i<10;i++)feed(1);
 return result;
}
test('a complete reference-like cycle counts once, standing never adds repetitions',()=>{
 const c=new RepCounter();drive(c);assert.equal(c.accepted,1);assert.equal(c.observed,1);
});
test('jitter, shallow movement and partial repetitions do not meet the target',()=>{
 for(const options of [{amplitude:.02},{amplitude:.2},{partial:true}]){
  const c=new RepCounter();drive(c,options);assert.equal(c.accepted,0);
 }
});
test('sustained wrong alignment or missing comparison points cannot count as matched',()=>{
 for(const parts of [{leftKnee:{status:'red'},trunk:{status:'green'}},{leftKnee:{status:'grey'},trunk:{status:'green'}}]){
  const c=new RepCounter();drive(c,{parts});assert.equal(c.observed,1);assert.equal(c.accepted,0);
 }
});
test('sustained tracking loss breaks the cycle; reset preserves previously accepted repetitions',()=>{
 const c=new RepCounter();drive(c,{longGap:true});assert.equal(c.accepted,0);
 drive(c);assert.equal(c.accepted,1);c.reset();assert.equal(c.accepted,1);
});
test('one missed frame does not erase a complete otherwise reliable repetition',()=>{
 const c=new RepCounter();drive(c,{gap:true});assert.equal(c.accepted,1);
});
test('alerts require sustained evidence, clear on recovery and respect cooldown',()=>{
 const g=new AlertGate();assert.equal(g.update('alignment',0),false);
 assert.equal(g.update('alignment',.9),true);assert.equal(g.update('alignment',1),false);
 g.update(null,2);assert.equal(g.update('range',3,true),false);
 assert.equal(g.update('range',7,true),true);g.reset();
 assert.equal(g.update('tracking',8),false);
});
test('audio is optional and muted alerts produce no sound',async()=>{
 const coach=new AudioCoach();assert.equal(await coach.unlock(),false);
 coach.enabled=false;coach.update('range',0,true);
 assert.equal(coach.gate.last,-Infinity);
});

test('audio schedules two short tones and stops when the session stops',async()=>{
 const previous=globalThis.AudioContext,starts=[];
 globalThis.AudioContext=class {
  state='suspended';currentTime=10;destination={};
  async resume(){this.state='running';}async suspend(){this.state='suspended';}
  createOscillator(){return {frequency:{},connect(){},start(t){starts.push(t);},stop(){}};}
  createGain(){return {connect(){},gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}}};}
 };
 try{
  const coach=new AudioCoach();assert.equal(await coach.unlock(),true);
  coach.update('alignment',0);coach.update('alignment',1);coach.update('alignment',2);
  assert.deepEqual(starts,[10,10.22]);coach.stop();coach.update('range',8,true);
  assert.equal(starts.length,2);
 }finally{if(previous===undefined)delete globalThis.AudioContext;else globalThis.AudioContext=previous;}
});
