// Reads short coaching lines aloud with the browser's built-in speech engine.
// Lines wait their turn: one plays at a time, never cut off and never on top of another.
// The wait is kept short, so a line that waited too long is dropped instead of arriving late.
const ARABIC=/[؀-ۿ]/;
export const REPEAT_SECONDS=6,STALE_SECONDS=3,MAX_WAITING=2;

const LINES={
 en:{good:'Good form.',knee:'Watch your knee.',trunk:'Chest up.',form:'Check your form.',view:'Step back into view.',depth:'Go a bit deeper.',pace:'Slow down.'},
 ar:{good:'أداء ممتاز.',knee:'انتبه لركبتك.',trunk:'ارفع صدرك.',form:'راجع حركتك.',view:'ارجع للخلف ليظهر جسمك.',depth:'انزل أكثر قليلًا.',pace:'أبطئ قليلًا.'},
};

function correction(issue,feedback,words){
 if(issue==='tracking')return words.view;
 if(issue==='range')return words.depth;
 if(issue==='tempo')return words.pace;
 if(issue==='alignment'){
  const parts=feedback?.parts||{},off=name=>['red','yellow'].includes(parts[name]?.status);
  return off('leftKnee')||off('rightKnee')?words.knee:off('trunk')?words.trunk:words.form;
 }
 return null;
}

// What to say for one frame of live feedback, or null to stay quiet.
// Only a correction to the pose, or praise for a repetition done well.
export function spokenLine(outcome,feedback,counted,lang='en'){
 const words=LINES[lang==='ar'?'ar':'en'];
 const fix=correction(outcome?.issue,feedback,words);
 if(outcome?.completed){
  if(outcome.counted&&outcome.accepted&&!fix)return {text:words.good,priority:2,key:`good-${counted}`};
  return {text:fix||words.form,priority:2,key:fix||words.form};
 }
 if(fix)return {text:fix,priority:1,key:fix};
 return null;
}

// Higher scores sound more natural. Online "Natural" voices beat older on-device ones.
export function voiceScore(voice,lang){
 const name=voice.name||'';
 let score=0;
 if(/natural|neural/i.test(name))score+=40;
 if(/premium|enhanced/i.test(name))score+=30;
 if(/^google/i.test(name))score+=25;
 if(/online/i.test(name))score+=15;
 if(/espeak|compact/i.test(name))score-=50;
 if(voice.lang?.toLowerCase()===(lang==='ar'?'ar-sa':'en-us'))score+=5;
 if(voice.localService)score+=2;
 return score;
}

export class SpeechCoach {
 constructor({synth=globalThis.speechSynthesis,Utterance=globalThis.SpeechSynthesisUtterance,now=()=>performance.now()/1000,timer=(f,ms)=>globalThis.setTimeout(f,ms),clear=id=>globalThis.clearTimeout(id)}={}){
  // Wrapped: a browser timer called as a method of this object throws "Illegal invocation".
  
  this.synth=synth;this.Utterance=Utterance;this.now=now;this.timer=timer;this.clear=clear;this.enabled=true;this.reset();
 }
 get supported(){return Boolean(this.synth&&this.Utterance);}
 reset(){this.playing=null;this.queue=[];this.heard=new Map();if(this.watchdog)this.clear?.(this.watchdog);this.watchdog=null;}
 voice(lang){
  const voices=(this.synth?.getVoices?.()||[]).filter(v=>v.lang?.toLowerCase().startsWith(lang));
  return voices.sort((a,b)=>voiceScore(b,lang)-voiceScore(a,lang))[0]||null;
 }
 // Voices can load late, so an empty list is not proof that Arabic is missing.
 missing(lang){return this.supported&&(this.synth.getVoices?.().length||0)>0&&!this.voice(lang);}
 // Safari only speaks after speech has started inside a tap, so call this from the button press.
 unlock(){
  if(!this.supported)return false;
  const silent=new this.Utterance(' ');silent.volume=0;this.synth.cancel();this.synth.speak(silent);return true;
 }
 stop(){if(this.supported)this.synth.cancel();this.reset();}
 say(text,{priority=1,key=text}={}){
  text=String(text||'').trim();
  if(!this.enabled||!this.supported||!text)return false;
  const time=this.now(),last=this.heard.get(key);
  if(last!==undefined&&time-last<REPEAT_SECONDS)return false;
  if(this.queue.some(item=>item.key===key))return false;
  const item={text,priority,key,at:time};
  if(!this.playing)return this.play(item);
  this.queue.push(item);
  // Keep the wait short: drop the least important (then oldest) line.
  while(this.queue.length>MAX_WAITING){
   const lowest=this.queue.reduce((a,b)=>b.priority<a.priority?b:a);
   this.queue.splice(this.queue.indexOf(lowest),1);
  }
  return 'queued';
 }
 play(item){
  const lang=ARABIC.test(item.text)?'ar':'en',voice=this.voice(lang);
  if(lang==='ar'&&!voice)return false;
  const line=new this.Utterance(item.text);
  line.lang=lang==='ar'?'ar-SA':'en-US';line.rate=lang==='ar'?.95:1;if(voice)line.voice=voice;
  const done=()=>this.finished(line);
  line.onend=done;line.onerror=done;
  this.playing=line;this.heard.set(item.key,item.at);
  this.arm(line,(1.5+item.text.split(/\s+/).length*.35)*1000,0);
  this.synth.speak(line);
  return true;
 }
 // Some browsers never fire onend. Move on after a while, but never while the voice is still talking.
 arm(line,wait,tries){
  this.watchdog=this.timer?.(()=>{if(this.playing!==line)return;if(this.synth.speaking&&tries<6)this.arm(line,500,tries+1);else this.finished(line);},wait);
 }
 finished(line){
  if(this.playing!==line)return;
  if(this.watchdog)this.clear?.(this.watchdog);
  this.playing=null;this.watchdog=null;
  if(!this.enabled)return;
  const time=this.now();
  this.queue=this.queue.filter(item=>time-item.at<=STALE_SECONDS);
  const next=this.queue.shift();
  if(next)this.play(next);
 }
}
