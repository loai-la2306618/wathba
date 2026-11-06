// Keep the current workout across screen changes and refreshes in this tab.
// Opening an old report does not add it to the active workout.
export class Workout {
 constructor(storage){
  if(storage===undefined){try{storage=globalThis.sessionStorage;}catch{storage=null;}}
  this.storage=storage;this.ids=[];
  try{const saved=JSON.parse(storage?.getItem('wathba-workout')||'[]');if(Array.isArray(saved))this.ids=[...new Set(saved.filter(id=>typeof id==='string'&&/^[a-f0-9]{32}$/.test(id)))];}catch{}
 }
 remember(session){if(session?.id&&session.kind!=='reference'&&!this.ids.includes(session.id)){this.ids.push(session.id);this.persist();}}
 persist(){try{this.storage?.setItem('wathba-workout',JSON.stringify(this.ids));}catch{}}
 sessions(fallback){
  if(this.ids.length)return [...this.ids];
  if(fallback?.check_in?.session_ids?.length)return [...fallback.check_in.session_ids];
  return fallback?.id?[fallback.id]:[];
 }
 complete(ids){this.ids=this.ids.filter(id=>!ids.includes(id));this.persist();}
}
