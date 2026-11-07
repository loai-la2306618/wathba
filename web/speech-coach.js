// Reads short coaching lines aloud with the browser's built-in speech engine.
// A line is never cut off: while one is playing, only the newest waiting line is kept,
// and it plays next if it is still fresh. A rep count outranks a correction.
const ARABIC=/[؀-ۿ]/;
export const REPEAT_SECONDS=6,STALE_SECONDS=2.5,COUNT_STALE_SECONDS=4;

const LINES={
 en:{good:'Good form.',notCounted:'Not counted.',knee:'Watch your knee.',trunk:'Chest up.',form:'Check your form.',view:'Step back into view.',depth:'Match the depth.',pace:'Match the pace.'},
 ar:{good:'أداء ممتاز.',notCounted:'لم يُحتسب.',knee:'انتبه لركبتك.',trunk:'ارفع صدرك.',form:'راجع حركتك.',view:'ارجع للخلف ليظهر جسمك.',depth:'اتبع عمق الحركة.',pace:'اتبع سرعة الحركة.'},
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
export function spokenLine(outcome,feedback,counted,lang='en'){
 const words=LINES[lang==='ar'?'ar':'en'];
 const fix=correction(outcome?.issue,feedback,words);
 if(outcome?.completed){
  if(outcome.counted)return {text:[`${counted}.`,outcome.accepted?words.good:fix].filter(Boolean).join(' '),priority:3,key:`rep-${counted}`};
  return {text:fix||words.notCounted,priority:2,key:`missed-${fix}`};
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
 constructor({synth=globalThis.speechSynthesis,Utterance=globalThis.SpeechSynthesisUtterance,now=()=>performance.now()/1000,timer=globalThis.setTimeout,clear=globalThis.clearTimeout}={}){
  this.synth=synth;this.Utterance=Utterance;this.now=now;this.timer=timer;this.clear=clear;this.enabled=true;this.reset();
 }
 get supported(){return Boolean(this.synth&&this.Utterance);}
 reset(){this.playing=null;this.pending=null;this.heard=new Map();if(this.watchdog)this.clear?.(this.watchdog);this.watchdog=null;}
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
  const item={text,priority,key,at:time};
  if(this.playing){
   if(!this.pending||priority>=this.pending.priority)this.pending=item;
   return 'queued';
  }
  return this.play(item);
 }
 play(item){
  const lang=ARABIC.test(item.text)?'ar':'en',voice=this.voice(lang);
  if(lang==='ar'&&!voice)return false;
  const line=new this.Utterance(item.text);
  line.lang=lang==='ar'?'ar-SA':'en-US';line.rate=lang==='ar'?.95:1;if(voice)line.voice=voice;
  const done=()=>this.finished(line);
  line.onend=done;line.onerror=done;
  this.playing=line;this.heard.set(item.key,item.at);
  // Some browsers never fire onend. Allow about a third of a second per word, plus a margin.
  this.watchdog=this.timer?.(done,(1.5+item.text.split(/\s+/).length*.35)*1000);
  this.synth.speak(line);
  return true;
 }
 finished(line){
  if(this.playing!==line)return;
  if(this.watchdog)this.clear?.(this.watchdog);
  this.playing=null;this.watchdog=null;
  const next=this.pending;this.pending=null;
  if(!next||!this.enabled)return;
  const age=this.now()-next.at;
  if(age<=(next.priority>=3?COUNT_STALE_SECONDS:STALE_SECONDS))this.play(next);
 }
}
