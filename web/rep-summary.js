import {countsTowardTarget} from './rep-counter.js';

export function repetitionSummary(session){
 const cycles=session.cycles||[];
 const scores=new Map((session.match_score?.per_repetition||[]).map(r=>[r.rep,r.value]));
 return {
  observed:session.repetitions??cycles.length,
  correct:session.accepted_repetitions??cycles.filter(c=>c.accepted===true).length,
  counted:session.counted_repetitions??cycles.filter(c=>c.comparison_assessable!==false&&countsTowardTarget(scores.get(c.rep))).length
 };
}

export function repetitionSummaryText(session,language='en'){
 const {observed,correct}=repetitionSummary(session);
 return language==='ar'?`عملت ${observed} عدات، منهم ${correct} صح حسب مرجع المعالج.`:`You did ${observed} reps; ${correct} matched the therapist reference.`;
}
