// Reference-relative screen measurements on the shared pose schema (named joints).
// Colours describe differences from a demonstration, not safety. All values are
// 2D image-plane estimates and change with camera position.
import {joint} from './pose/schema.js';

export const COLOURS={green:'#89f5b0',grey:'#9da5af',yellow:'#ffd66b',red:'#ff6d78'};
const PARTS={
 leftKnee:['left_hip','left_knee','left_ankle'],
 rightKnee:['right_hip','right_knee','right_ankle'],
 trunk:['left_shoulder','right_shoulder','left_hip','right_hip'],
};
const reliable=(pose,names)=>names.every(n=>joint(pose,n));

export function measurements(pose){
 const values={};
 if(!pose?.keypoints)return values;
 const {width=1,height=1}=pose.frame||{},px=n=>{const k=joint(pose,n);return [k.x*width,k.y*height];};
 for(const part of ['leftKnee','rightKnee']){
  const [hip,knee,ankle]=PARTS[part];
  if(!reliable(pose,[hip,knee,ankle]))continue;
  const A=px(hip),B=px(knee),C=px(ankle),dx=C[0]-A[0],dy=C[1]-A[1],d=dx*dx+dy*dy;
  if(d>0)values[part]=Math.abs(dx*(B[1]-A[1])-dy*(B[0]-A[0]))/d;
 }
 if(reliable(pose,['left_shoulder','left_hip'])){
  const s=px('left_shoulder'),h=px('left_hip');
  values.trunk=Math.atan2(Math.abs(s[0]-h[0]),Math.abs(h[1]-s[1]))*180/Math.PI;
 }
 return values;
}
export function compareParts(values,expected,tolerances={}){
 const parts={};
 for(const part of Object.keys(PARTS)){
  const v=values[part],e=expected?.[part],t=tolerances[part]??(part==='trunk'?12:.08);
  if(!Number.isFinite(v)||!Number.isFinite(e)||!(t>0)){parts[part]={status:'grey'};continue;}
  const ratio=Math.abs(v-e)/t;
  parts[part]={status:ratio>2?'red':ratio>1?'yellow':'green',observed:v,reference:e,ratio};
 }
 return parts;
}
export function edgePart(a,b){
 return Object.entries(PARTS).find(([,names])=>names.includes(a)&&names.includes(b))?.[0]??null;
}
export function colourForEdge(a,b,pose,parts){
 if(!reliable(pose,[a,b]))return COLOURS.grey;
 return COLOURS[parts?.[edgePart(a,b)]?.status||'grey'];
}
export function evaluateLive(pose,context){
 const {model,referenceRows=[],referenceCycles=[],depth=0,returning=false}=context;
 if(!model||!referenceCycles.length)return {parts:compareParts(measurements(pose),{}),title:'Movement tracking',message:'No fitted reference for this exercise. Your recording will be saved for therapist review.'};
 const primary=model.templates[model.primary_feature],curve=primary?.median;
 if(!curve)return {parts:compareParts({},{}),title:'Reference unavailable',message:'Your therapist needs to prepare this exercise reference.'};
 const peak=curve.reduce((best,v,i)=>Math.abs(v)>Math.abs(curve[best])?i:best,0);
 const start=returning?peak:0,end=returning?curve.length-1:peak;
 let index=start;
 for(let i=start;i<=end;i++)if(Math.abs(curve[i]-depth)<Math.abs(curve[index]-depth))index=i;
 const phase=index/(curve.length-1),cycle=referenceCycles[0],time=cycle.start+phase*cycle.duration;
 const row=referenceRows.reduce((best,r)=>Math.abs(r.time-time)<Math.abs((best?.time??Infinity)-time)?r:best,null);
 const expected=row?.keypoints?measurements({...row,frame:pose?.frame}):{},tolerances={};
 if(model.templates.knee_offset){expected.leftKnee=model.templates.knee_offset.median[index];tolerances.leftKnee=Math.max(.08,model.templates.knee_offset.spread[index]*3,model.templates.knee_offset.tolerance);}
 if(model.templates.torso_lean){expected.trunk=model.templates.torso_lean.median[index];tolerances.trunk=Math.max(12,model.templates.torso_lean.spread[index]*3,model.templates.torso_lean.tolerance);}
 const parts=compareParts(measurements(pose),expected,tolerances);
 // A right-side template is not fitted by our left-side comparison profile.
 parts.rightKnee={status:'grey'};
 const issue=Object.entries(parts).filter(([,v])=>['red','yellow'].includes(v.status)).sort((a,b)=>b[1].ratio-a[1].ratio)[0];
 if(issue){const name=issue[0]==='trunk'?'trunk':'left knee';return {parts,title:issue[1].status==='red'?'Pause and reset':'Check your alignment',message:`Your ${name} differs from the demonstrated position. Compare with your therapist’s guide within your assigned limits.`};}
 const good=Object.values(parts).some(v=>v.status==='green');
 return {parts,title:good?'Following the reference':'Check camera view',message:good?'Tracked parts are within the current reference tolerance. Keep your assigned pace.':'Step back until your shoulders, knees and feet are visible.'};
}
