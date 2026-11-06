import {AlertGate} from './rep-counter.js';

export class AudioCoach {
 constructor(){this.enabled=true;this.active=false;this.gate=new AlertGate();this.nodes=new Set();}
 async unlock(){
  try{
   const Context=globalThis.AudioContext||globalThis.webkitAudioContext;
   if(!Context)return false;
   this.context??=new Context();await this.context.resume();
   this.active=this.context.state==='running';return this.active;
  }catch{return false;}
 }
 reset(){this.gate.reset();}
 stop(){this.active=false;this.gate.reset();for(const node of this.nodes){try{node.stop();}catch{}}this.nodes.clear();}
 async preview(){if(!await this.unlock())return false;this.play();return true;}
 update(issue,time,immediate=false){
  if(!this.enabled||!this.active||this.context?.state!=='running'||!this.gate.update(issue,time,immediate))return;
  this.play();
 }
 play(){
  if(this.context?.state!=='running')return;
  // Two short tones; no server or speech service is needed.
  const now=this.context.currentTime;
  for(const offset of [0,.22]){
   const oscillator=this.context.createOscillator(),gain=this.context.createGain();
   oscillator.frequency.value=660;oscillator.connect(gain);gain.connect(this.context.destination);
   this.nodes.add(oscillator);oscillator.onended=()=>{this.nodes.delete(oscillator);oscillator.disconnect?.();gain.disconnect?.();};
   gain.gain.setValueAtTime(0,now+offset);gain.gain.linearRampToValueAtTime(.12,now+offset+.02);
   gain.gain.exponentialRampToValueAtTime(.001,now+offset+.16);
   oscillator.start(now+offset);oscillator.stop(now+offset+.18);
  }
 }
}
