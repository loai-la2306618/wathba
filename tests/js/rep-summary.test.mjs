import test from 'node:test';
import assert from 'node:assert/strict';
import {repetitionSummary,repetitionSummaryText} from '../../web/rep-summary.js';

test('summary reports five observed and three correct independently of the 60% counter',()=>{
 const session={repetitions:5,accepted_repetitions:3,counted_repetitions:4};
 assert.deepEqual(repetitionSummary(session),{observed:5,correct:3,counted:4});
 assert.equal(repetitionSummaryText(session,'ar'),'عملت 5 عدات، منهم 3 صح حسب مرجع المعالج.');
});
test('score threshold includes 60 and excludes low-score and unassessable repetitions',()=>{
 const cycles=[1,2,3,4].map(rep=>({rep,comparison_assessable:rep!==4,accepted:rep===2}));
 const session={repetitions:4,cycles,match_score:{per_repetition:[{rep:1,value:60},{rep:2,value:90},{rep:3,value:59},{rep:4,value:99}]}};
 assert.deepEqual(repetitionSummary(session),{observed:4,correct:1,counted:2});
});
