// Conservative live counter: stable rest -> excursion -> stable return.
// Accepted means within the fitted demonstration's tolerances, not clinical safety.
export const countsTowardTarget=score=>Number.isFinite(score)&&score>=60;
export class RepCounter {
 constructor(){this.accepted=0;this.counted=0;this.observed=0;this.reset();}
 reset(){this.rest=[];this.baseline=null;this.active=null;this.lastTime=null;this.filtered=null;this.previous=null;}
 update({time,height,parts={},features=null,reference,valid=true,finishing=false}){
  const template=reference?.templates?.hip_height;
  if(!template||!Number.isFinite(time)){
   this.reset();return {issue:'reference'};
  }
  if(!valid||!Number.isFinite(height)){
   // An isolated missed joint must not restart standing calibration forever.
   if(this.active){this.active.frames++;this.active.unknown++;}
   if(this.lastTime!==null&&time-this.lastTime>.5)this.reset();
   return {issue:'tracking'};
  }
  if(this.lastTime!==null&&((time<=this.lastTime&&!finishing)||time-this.lastTime>.5))this.reset();
  const dt=this.lastTime===null ? .1 : time-this.lastTime;
  this.lastTime=time;
  const alpha=1-Math.exp(-dt/.08);
  this.filtered=this.filtered===null?height:this.filtered+alpha*(height-this.filtered);
  height=this.filtered;
  if(this.baseline===null){
   this.rest.push({time,height});
   this.rest=this.rest.filter(p=>time-p.time<=.8);
   if(this.rest.length>=4&&time-this.rest[0].time>=.5){
    const values=this.rest.map(p=>p.height);
    if(Math.max(...values)-Math.min(...values)<Math.max(.06,Math.min(.12,template.tolerance||.12)))this.baseline=values.reduce((a,b)=>a+b)/values.length;
   }
   return {calibrating:true};
  }
  const depth=this.baseline-height,expected=template.excursion_median;
  const allowance=Math.max(template.tolerance||.12,3*(template.excursion_mad||0));
  const start=Math.max(.08,Math.min(.18,expected*.3));
  const end=Math.min(start*.8,Math.max(.04,Math.min(template.tolerance||.12,expected*.15)));
  const assessed=['leftKnee','trunk'].filter(p=>reference.templates[p==='trunk'?'torso_lean':'knee_offset']);
  const visible=assessed.length>0&&assessed.every(p=>parts[p]?.status&&parts[p].status!=='grey');
  const mismatch=assessed.some(p=>['yellow','red'].includes(parts[p]?.status));
  const sample={time,height,features};
  if(!this.active&&depth>start){
   const first=this.previous||sample;
   this.active={start:first.time,peak:depth,frames:0,bad:0,unknown:0,returnAt:null,samples:[first]};
  }
  this.previous=sample;
  const c=this.active;
  if(!c){this.baseline=Math.max(height,this.baseline*.99+height*.01);return {};}
  c.frames++;c.bad+=Number(mismatch);c.unknown+=Number(!visible);c.peak=Math.max(c.peak,depth);
  if(c.samples.at(-1).time<time)c.samples.push(sample);
  if(time-c.start>Math.max(8,reference.duration_median*3)){this.reset();return {issue:'tempo'};}
  if(depth>=end){c.returnAt=null;return {active:true,depth,issue:mismatch?'alignment':null};}
  c.returnAt??=time;
  if(!finishing&&time-c.returnAt<.15)return {active:true,depth};
  const duration=c.returnAt-c.start,tempoAllowance=Math.max(.35,reference.duration_median*.25,3*(reference.duration_mad||0));
  const rangeOK=Math.abs(c.peak-expected)<=allowance&&c.peak>=expected*.6;
  const tempoOK=Math.abs(duration-reference.duration_median)<=tempoAllowance;
  const comparison=features?compareRepetition(c.samples.filter(s=>s.time<=c.returnAt),reference):null;
  const issue=comparison?(!comparison.assessable?'tracking':!tempoOK?'tempo':comparison.issue):!rangeOK?'range':!tempoOK?'tempo':c.unknown/c.frames>.2?'tracking':c.bad/c.frames>=.25?'alignment':null;
  const accepted=issue===null;
  const score=comparison?.score??(accepted?100:null);
  const counted=countsTowardTarget(score)&&(!comparison||comparison.assessable);
  this.observed++;if(accepted)this.accepted++;
  if(counted)this.counted++;
  this.active=null;
  return {completed:true,accepted,counted,score,duration,issue};
 }
}

// Use the same phase resampling, constrained DTW, range and sustained-difference
// tolerances as the final Python assessment. Instantaneous cue colours alone
// cannot decide whether a complete repetition matches a reference.
export function compareRepetition(samples,reference){
 if(samples.length<3)return {assessable:false};
 const start=samples[0].time,duration=samples.at(-1).time-start;
 if(duration<=0)return {assessable:false};
 let issue=null,weightedScore=0,totalWeight=0;
 for(const [name,template] of Object.entries(reference.templates)){
  const rows=samples.filter(s=>Number.isFinite(name==='hip_height'?s.height:s.features?.[name]));
  if(rows.length<3||rows.length/samples.length<.8||rows[0].time>start+duration*.15||rows.at(-1).time<start+duration*.85)return {assessable:false};
  if(rows.some((s,i)=>i&&s.time-rows[i-1].time>.5))return {assessable:false};
  const expected=template.median;
  if(!Array.isArray(expected)||expected.length<3||!Array.isArray(template.spread)||template.spread.length!==expected.length)return {assessable:false};
  const n=expected.length,observed=[];
  let cursor=0;
  const value=s=>name==='hip_height'?s.height:s.features[name];
  for(let i=0;i<n;i++){
   const t=start+duration*i/(n-1);
   while(cursor<rows.length-2&&rows[cursor+1].time<t)cursor++;
   const a=rows[cursor],b=rows[Math.min(cursor+1,rows.length-1)];
   const fraction=b.time===a.time?0:Math.max(0,Math.min(1,(t-a.time)/(b.time-a.time)));
   observed.push(value(a)+(value(b)-value(a))*fraction);
  }
  if(name==='hip_height'){const origin=observed[0];for(let i=0;i<n;i++)observed[i]-=origin;}
  const path=alignCurves(expected,observed);
  const error=path.reduce((sum,[i,j])=>sum+Math.abs(expected[i]-observed[j])/Math.max(3*template.spread[i],template.tolerance),0)/path.length;
  const weight=name===reference.primary_feature?2:1;
  weightedScore+=100*Math.exp(-error)*weight;totalWeight+=weight;
  const outside=path.filter(([i,j])=>Math.abs(expected[i]-observed[j])>Math.max(3*template.spread[i],template.tolerance)).length/path.length;
  if(name===reference.primary_feature){
   const excursion=Math.max(...observed)-Math.min(...observed);
   if(Math.abs(excursion-template.excursion_median)>Math.max(3*template.excursion_mad,template.tolerance)){issue='range';continue;}
  }
  if(outside>=.25&&issue!=='range')issue='alignment';
 }
 const tempo=100*Math.exp(-Math.abs(Math.log(duration/reference.duration_median)));
 const score=totalWeight&&Number.isFinite(tempo)?Math.round(.8*weightedScore/totalWeight+.2*tempo):null;
 return {assessable:true,issue,score};
}

function alignCurves(a,b){
 const n=a.length,m=b.length,band=Math.max(Math.abs(n-m),Math.floor(Math.max(n,m)*.2));
 const costs=Array.from({length:n+1},()=>new Float64Array(m+1).fill(Infinity));costs[0][0]=0;
 for(let i=1;i<=n;i++)for(let j=Math.max(1,i-band);j<=Math.min(m,i+band);j++)costs[i][j]=Math.abs(a[i-1]-b[j-1])+Math.min(costs[i-1][j],costs[i][j-1],costs[i-1][j-1]);
 const result=[];let i=n,j=m;
 while(i>0&&j>0){result.push([i-1,j-1]);const choices=[costs[i-1][j-1],costs[i-1][j],costs[i][j-1]],best=Math.min(...choices);if(choices[0]===best){i--;j--;}else if(choices[1]===best)i--;else j--;}
 return result.reverse();
}

export class AlertGate {
 constructor(){this.reset();}
 reset(){this.issue=null;this.since=null;this.last=-Infinity;}
 update(issue,time,immediate=false){
  if(issue!==this.issue){this.issue=issue;this.since=time;}
  if(!issue||(!immediate&&time-this.since<.8)||time-this.last<6)return false;
  this.last=time;return true;
 }
}
