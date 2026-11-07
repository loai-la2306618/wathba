import assert from 'node:assert/strict';
import test from 'node:test';
import {REPEAT_SECONDS, SpeechCoach, spokenLine, voiceScore} from '../../web/speech-coach.js';

function setup(voices = [{name: 'Basic', lang: 'en-US', localService: true}, {name: 'Arabic', lang: 'ar-SA', localService: true}]) {
  const said = [];
  const timers = [];
  const synth = {cancelled: 0, cancel() { this.cancelled++; }, speak(u) { said.push(u); }, getVoices: () => voices};
  class Utterance { constructor(text) { this.text = text; } }
  const clock = {t: 100};
  const coach = new SpeechCoach({synth, Utterance, now: () => clock.t, timer: (f) => { timers.push(f); return timers.length; }, clear() {}});
  return {coach, said, synth, clock, timers};
}

const end = (said) => said.at(-1).onend();

test('a line is never cut off: the newest waiting line plays when it finishes', () => {
  const {coach, said, synth, clock} = setup();
  coach.say('Watch your knee.');
  assert.equal(coach.say('Chest up.'), 'queued');
  assert.equal(coach.say('Match the pace.'), 'queued');
  assert.equal(synth.cancelled, 0);
  clock.t += 1;
  end(said);
  assert.deepEqual(said.map(u => u.text), ['Watch your knee.', 'Match the pace.']);
});

test('a rep count outranks a waiting correction', () => {
  const {coach, said, clock} = setup();
  coach.say('Watch your knee.', {priority: 1});
  coach.say('3. Good form.', {priority: 3, key: 'rep-3'});
  coach.say('Chest up.', {priority: 1});
  clock.t += 1;
  end(said);
  assert.equal(said.at(-1).text, '3. Good form.');
});

test('a correction that waited too long is dropped', () => {
  const {coach, said, clock} = setup();
  coach.say('Watch your knee.');
  coach.say('Chest up.');
  clock.t += 5;
  end(said);
  assert.equal(said.length, 1);
});

test('the same correction is not repeated within the repeat gap', () => {
  const {coach, said, clock} = setup();
  coach.say('Watch your knee.');
  end(said);
  clock.t += 2;
  assert.equal(coach.say('Watch your knee.'), false);
  clock.t = 100 + REPEAT_SECONDS + 1;
  assert.equal(coach.say('Watch your knee.'), true);
});

test('a browser that never reports the end still moves on', () => {
  const {coach, said, clock, timers} = setup();
  coach.say('Watch your knee.');
  coach.say('Chest up.');
  clock.t += 1;
  timers[0]();
  assert.equal(said.at(-1).text, 'Chest up.');
});

test('the most natural voice is chosen', () => {
  const {coach} = setup([{name: 'Microsoft David', lang: 'en-US', localService: true}, {name: 'Microsoft Aria Online (Natural)', lang: 'en-US', localService: false}, {name: 'eSpeak English', lang: 'en-US', localService: true}]);
  assert.equal(coach.voice('en').name, 'Microsoft Aria Online (Natural)');
  assert.ok(voiceScore({name: 'Google UK English Female', lang: 'en-GB'}, 'en') > voiceScore({name: 'Microsoft Zira', lang: 'en-US', localService: true}, 'en'));
});

test('Arabic uses an Arabic voice and is skipped when the device has none', () => {
  const withVoice = setup();
  withVoice.coach.say('انتبه لركبتك.');
  assert.equal(withVoice.said[0].lang, 'ar-SA');
  const without = setup([{name: 'Basic', lang: 'en-US'}]);
  assert.equal(without.coach.say('انتبه لركبتك.'), false);
  assert.equal(without.coach.missing('ar'), true);
  assert.equal(setup([]).coach.missing('ar'), false);
});

test('spoken lines are short: count, good form or one correction', () => {
  const knee = {parts: {leftKnee: {status: 'red'}, trunk: {status: 'green'}}};
  assert.equal(spokenLine({completed: true, counted: true, accepted: true}, knee, 3).text, '3. Good form.');
  assert.equal(spokenLine({completed: true, counted: true, accepted: false, issue: 'alignment'}, knee, 4).text, '4. Watch your knee.');
  assert.equal(spokenLine({completed: true, counted: false, issue: 'range'}, knee, 4).text, 'Match the depth.');
  assert.equal(spokenLine({completed: true, counted: false, issue: null}, knee, 4).text, 'Not counted.');
  assert.equal(spokenLine({active: true, issue: 'alignment'}, {parts: {trunk: {status: 'yellow'}}}, 2).text, 'Chest up.');
  assert.equal(spokenLine({issue: 'tracking'}, {}, 0).text, 'Step back into view.');
  assert.equal(spokenLine({calibrating: true}, {}, 0), null);
  assert.equal(spokenLine({issue: 'reference'}, {}, 0), null);
  assert.equal(spokenLine({completed: true, counted: true, accepted: true}, knee, 5, 'ar').text, '5. أداء ممتاز.');
  for (const line of [spokenLine({issue: 'tracking'}, {}, 0, 'ar'), spokenLine({issue: 'tempo'}, {}, 0)]) assert.ok(line.text.split(' ').length <= 5);
});

test('muted or unsupported speech stays silent and does not throw', () => {
  const {coach, said} = setup();
  coach.enabled = false;
  assert.equal(coach.say('Good form.'), false);
  assert.equal(said.length, 0);
  const none = new SpeechCoach({synth: undefined, Utterance: undefined, now: () => 1});
  assert.equal(none.say('Good form.'), false);
  assert.equal(none.unlock(), false);
  none.stop();
});
