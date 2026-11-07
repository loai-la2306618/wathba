// Reads the live comments aloud with the browser's built-in speech engine.
// Comments never queue up: an old comment is dropped, and a warning can interrupt a calmer one.
const ARABIC=/[؀-ۿ]/;
export const REPEAT_SECONDS=9,GAP_SECONDS=3,INTERRUPT_SECONDS=1.2;

export class SpeechCoach {
 constructor({synth=globalThis.speechSynthesis,Utterance=globalThis.SpeechSynthesisUtterance,now=()=>performance.now()/1000}={}){
  this.synth=synth;this.Utterance=Utterance;this.now=now;this.enabled=true;this.reset();
 }
 get supported(){return Boolean(this.synth&&this.Utterance);}
 reset(){this.last='';this.lastAt=-Infinity;}
 voice(lang){
  const voices=this.synth?.getVoices?.()||[],matching=voices.filter(v=>v.lang?.toLowerCase().startsWith(lang));
  return matching.find(v=>v.localService)||matching[0]||null;
 }
 // Voices can load late, so an empty list is not proof that Arabic is missing.
 missing(lang){return this.supported&&(this.synth.getVoices?.().length||0)>0&&!this.voice(lang);}
 // Safari only speaks after speech has started inside a tap, so call this from the button press.
 unlock(){
  if(!this.supported)return false;
  const silent=new this.Utterance(' ');silent.volume=0;this.synth.cancel();this.synth.speak(silent);return true;
 }
 stop(){this.reset();if(this.supported)this.synth.cancel();}
 say(comment,{urgent=false}={}){
  const text=String(comment||'').trim(),time=this.now();
  if(!this.enabled||!this.supported||!text)return false;
  if(text===this.last&&time-this.lastAt<REPEAT_SECONDS)return false;
  if(urgent?time-this.lastAt<INTERRUPT_SECONDS:this.synth.speaking||time-this.lastAt<GAP_SECONDS)return false;
  const lang=ARABIC.test(text)?'ar':'en',voice=this.voice(lang);
  if(lang==='ar'&&!voice)return false;
  if(this.synth.speaking)this.synth.cancel();
  const line=new this.Utterance(text);
  line.lang=lang==='ar'?'ar-SA':'en-US';line.rate=1;if(voice)line.voice=voice;
  this.synth.speak(line);this.last=text;this.lastAt=time;return true;
 }
}
