// Reference-relative screen measurements. Colours describe differences, not safety.
export const COLOURS={green:'#89f5b0',grey:'#9da5af',yellow:'#ffd66b',red:'#ff6d78'};
const visible=(p,ids)=>ids.every(i=>p?.[i]?.visibility>=.45&&p[i].x>=-.05&&p[i].x<=1.05&&p[i].y>=-.05&&p[i].y<=1.05);
export function measurements(p,width=1,height=1){
 const pixel=i=>[p[i].x*width,p[i].y*height];
 const values={};
 for(const [name,a,b,c] of [['leftKnee',23,25,27],['rightKnee',24,26,28]]){
  if(!visible(p,[a,b,c]))continue;
  const A=pixel(a),B=pixel(b),C=pixel(c),dx=C[0]-A[0],dy=C[1]-A[1],d=dx*dx+dy*dy;
  if(d>0)values[name]=Math.abs(dx*(B[1]-A[1])-dy*(B[0]-A[0]))/d;
 }
 if(visible(p,[11,23]))values.trunk=Math.atan2(Math.abs((p[11].x-p[23].x)*width),Math.abs((p[23].y-p[11].y)*height))*180/Math.PI;
 return values;
}
export function compareParts(values,expected,tolerances={}){
 const parts={};
 for(const part of ['leftKnee','rightKnee','trunk']){
  const v=values[part],e=expected?.[part],t=tolerances[part]??(part==='trunk'?12:.08);
  if(!Number.isFinite(v)||!Number.isFinite(e)||!(t>0)){parts[part]={status:'grey'};continue;}
  const ratio=Math.abs(v-e)/t;
  parts[part]={status:ratio>2?'red':ratio>1?'yellow':'green',observed:v,reference:e,ratio};
 }
 return parts;
}
export function edgePart(a,b){
 if([23,25,27,29,31].includes(a)&&[23,25,27,29,31].includes(b))return 'leftKnee';
 if([24,26,28,30,32].includes(a)&&[24,26,28,30,32].includes(b))return 'rightKnee';
 if([11,12,23,24].includes(a)&&[11,12,23,24].includes(b))return 'trunk';
 return null;
}
export function colourForEdge(a,b,points,parts){
 if(!visible(points,[a,b]))return COLOURS.grey;
 return COLOURS[parts?.[edgePart(a,b)]?.status||'grey'];
}
export function evaluateLive(points,context){
 const {model,referenceRows=[],referenceCycles=[],depth=0,returning=false,width=1,height=1}=context;
 if(!model||!referenceCycles.length)return {parts:compareParts(measurements(points,width,height),{}),title:'Movement tracking',message:'No fitted reference for this exercise. Your recording will be saved for therapist review.'};
 const primary=model.templates[model.primary_feature],curve=primary?.median;
 if(!curve)return {parts:compareParts({},{}),title:'Reference unavailable',message:'Your therapist needs to prepare this exercise reference.'};
 const peak=curve.reduce((best,v,i)=>Math.abs(v)>Math.abs(curve[best])?i:best,0);
 const start=returning?peak:0,end=returning?curve.length-1:peak;
 let index=start;
 for(let i=start;i<=end;i++)if(Math.abs(curve[i]-depth)<Math.abs(curve[index]-depth))index=i;
 const phase=index/(curve.length-1),cycle=referenceCycles[0],time=cycle.start+phase*cycle.duration;
 const row=referenceRows.reduce((best,r)=>Math.abs(r.time-time)<Math.abs((best?.time??Infinity)-time)?r:best,null);
 const expected=measurements(row?.landmarks||[],width,height),tolerances={};
 if(model.templates.knee_offset){expected.leftKnee=model.templates.knee_offset.median[index];tolerances.leftKnee=Math.max(.08,model.templates.knee_offset.spread[index]*3,model.templates.knee_offset.tolerance);}
 if(model.templates.torso_lean){expected.trunk=model.templates.torso_lean.median[index];tolerances.trunk=Math.max(12,model.templates.torso_lean.spread[index]*3,model.templates.torso_lean.tolerance);}
 const parts=compareParts(measurements(points,width,height),expected,tolerances);
 // A right-side template is not fitted by our left-side comparison profile.
 parts.rightKnee={status:'grey'};
 const issue=Object.entries(parts).filter(([,v])=>['red','yellow'].includes(v.status)).sort((a,b)=>b[1].ratio-a[1].ratio)[0];
 if(issue){const name=issue[0]==='trunk'?'trunk':'left knee';return {parts,title:issue[1].status==='red'?'Pause and reset':'Check your alignment',message:`Your ${name} differs from the demonstrated position. Compare with your therapist’s guide within your assigned limits.`};}
 const good=Object.values(parts).some(v=>v.status==='green');
 return {parts,title:good?'Following the reference':'Check camera view',message:good?'Tracked parts are within the current reference tolerance. Keep your assigned pace.':'Step back until your shoulders, knees and feet are visible.'};
}
