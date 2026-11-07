import test from 'node:test';
import assert from 'node:assert/strict';
import {Workout} from '../../web/workout.js';

function memory(){const values=new Map();return {getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};}
test('all completed exercises stay grouped across screens and refresh until evaluation is saved',()=>{
 const storage=memory(),w=new Workout(storage),first={id:'a'.repeat(32)},second={id:'b'.repeat(32)};
 w.remember(first);w.remember(second);w.remember(first);
 const restored=new Workout(storage);
 assert.deepEqual(restored.sessions(second),[first.id,second.id]);
 restored.complete([first.id,second.id]);
 assert.deepEqual(new Workout(storage).ids,[]);
});
test('opening a saved report alone does not join the active workout, and references are excluded',()=>{
 const w=new Workout(memory());w.remember({id:'a'.repeat(32),kind:'reference'});
 assert.deepEqual(w.ids,[]);
 const old={id:'b'.repeat(32),check_in:{session_ids:['b'.repeat(32),'c'.repeat(32)]}};
 assert.deepEqual(w.sessions(old),old.check_in.session_ids);
 assert.deepEqual(w.ids,[]);
});
test('failed evaluation keeps the pending exercises; completing a snapshot preserves newer recordings',()=>{
 const w=new Workout(memory());w.remember({id:'a'.repeat(32)});const snapshot=w.sessions();
 w.remember({id:'b'.repeat(32)});assert.equal(w.ids.length,2);
 w.complete(snapshot);assert.deepEqual(w.ids,['b'.repeat(32)]);
});
