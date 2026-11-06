import {icon} from '/static/icons.js';
const $=id=>document.getElementById(id);
const dueLabel=date=>new Intl.DateTimeFormat('en',{timeZone:'Asia/Qatar',weekday:'short',month:'short',day:'numeric'}).format(new Date(date+'T12:00:00+03:00'));
export function renderProgram(program,onSelect,onReview){
 if(!program)return;
 $('program-score').textContent=`${program.completed}/${program.total}`;
 $('program-ring').style.setProperty('--progress',program.progress);$('program-ring').title='Exercises completed today';
 $('program-fill').style.width=`${program.progress}%`;
 $('demo-program-fill').style.width=`${program.progress}%`;
 $('demo-program-progress').textContent=`${program.completed} of ${program.total} exercises completed today`;
 $('today-plan').textContent=`${program.completed}/2 completed today · 4 sessions / week`;
 $('demo-next').innerHTML=`${icon('clock')}<div><strong>Next scheduled session</strong><span>${dueLabel(program.next_due)} · Doha time</span></div>`;
 $('demo-exercises').innerHTML=program.exercises.map(e=>`<article class="program-exercise ${e.completed?'is-complete':''}"><button class="exercise-list-row" data-load-exercise="${e.id}"><span class="exercise-thumb ${e.id==='squat'?'tile-1':'jump-thumb'}">${e.id==='jump'?icon('accessibility'):''}</span><div><strong>${e.name}</strong><span>${e.completed?'Completed today':`${e.repetitions_today}/${e.target} reps today`} · ${e.target} rep target</span><span>Next: ${dueLabel(e.next_due)}</span></div><span class="round-play">${icon(e.completed?'check':'arrow-right-up')}</span></button>${e.last_session?`<button class="text-button" data-recording="${e.last_session}">${icon('play')}Review last recording</button>`:''}</article>`).join('');
 $('demo-exercises').querySelectorAll('[data-load-exercise]').forEach(b=>b.onclick=()=>onSelect(b.dataset.loadExercise));
 $('demo-exercises').querySelectorAll('[data-recording]').forEach(b=>b.onclick=()=>onReview(b.dataset.recording));
}
