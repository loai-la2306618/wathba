import assert from 'node:assert/strict';
import test from 'node:test';
import {REPEAT_SECONDS, STALE_SECONDS, SpeechCoach, spokenLine, voiceScore} from '../../web/speech-coach.js';

function setup(voices = [{name: 'Basic', lang: 'en-US', localService: true}, {name: 'Arabic', lang: 'ar-SA', localService: true}]) {
  const said = [];
  const timers = [];
  const synth = {cancelled: 0, speaking: false, cancel() { this.cancelled++; }, speak(u) { said.push(u); }, getVoices: () => voices};
  class Utterance { constructor(text) { this.text = text; } }
  const clock = {t: 100};
  const coach = new SpeechCoach({synth, Utterance, now: () => clock.t, timer: (f) => { timers.push(f); return timers.length; }, clear() {}});
  return {coach, said, synth, clock, timers};
}

const end = (said) => said.at(-1).onend();

test('lines wait their turn and play in order, never on top of each other', () => {
  const {coach, said, synth, clock} = setup();
  coach.say('Watch your knee.');
  assert.equal(coach.say('Chest up.'), 'queued');
  assert.equal(said.length, 1);
  assert.equal(synth.cancelled, 0);
  clock.t += 1;
  end(said);
  assert.deepEqual(said.map(u => u.text), ['Watch your knee.', 'Chest up.']);
});

test('the wait stays short: the least important line is dropped first', () => {
  const {coach, said, clock} = setup();
  coach.say('Watch your knee.', {priority: 1});
  coach.say('Chest up.', {priority: 1});
  coach.say('Good form.', {priority: 2, key: 'good-3'});
  coach.say('Slow down.', {priority: 1});
  clock.t += 1;
  end(said);
  clock.t += 1;
  end(said);
  assert.deepEqual(said.map(u => u.text), ['Watch your knee.', 'Good form.', 'Slow down.']);
});

test('a line that waited too long is dropped', () => {
  const {coach, said, clock} = setup();
  coach.say('Watch your knee.');
  coach.say('Chest up.');
  clock.t += STALE_SECONDS + 1;
  end(said);
  assert.equal(said.length, 1);
});

test('the same line is not repeated or queued twice', () => {
  const {coach, said, clock} = setup();
  coach.say('Watch your knee.');
  coach.say('Chest up.');
  assert.equal(coach.say('Chest up.'), false);
  end(said);
  end(said);
  clock.t += 2;
  assert.equal(coach.say('Watch your knee.'), false);
  clock.t = 100 + REPEAT_SECONDS + 1;
  assert.equal(coach.say('Watch your knee.'), true);
});

test('a browser that never reports the end moves on, but not while the voice still talks', () => {
  const {coach, said, synth, clock, timers} = setup();
  coach.say('Watch your knee.');
  coach.say('Chest up.');
  clock.t += 1;
  synth.speaking = true;
  timers.at(-1)();
  assert.equal(said.length, 1);
  synth.speaking = false;
  timers.at(-1)();
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

test('spoken lines only correct the pose or praise it, with no counts', () => {
  const knee = {parts: {leftKnee: {status: 'red'}, trunk: {status: 'green'}}};
  const clean = {parts: {}};
  assert.equal(spokenLine({completed: true, counted: true, accepted: true}, clean, 3).text, 'Good form.');
  assert.equal(spokenLine({completed: true, counted: true, accepted: false, issue: 'alignment'}, knee, 4).text, 'Watch your knee.');
  assert.equal(spokenLine({completed: true, counted: false, issue: 'range'}, knee, 4).text, 'Go a bit deeper.');
  assert.equal(spokenLine({completed: true, counted: false, issue: null}, clean, 4).text, 'Check your form.');
  assert.equal(spokenLine({active: true, issue: 'alignment'}, {parts: {trunk: {status: 'yellow'}}}, 2).text, 'Chest up.');
  assert.equal(spokenLine({issue: 'tracking'}, {}, 0).text, 'Step back into view.');
  assert.equal(spokenLine({calibrating: true}, {}, 0), null);
  assert.equal(spokenLine({issue: 'reference'}, {}, 0), null);
  assert.equal(spokenLine({completed: true, counted: true, accepted: true}, clean, 5, 'ar').text, 'أداء ممتاز.');
  assert.notEqual(spokenLine({completed: true, counted: true, accepted: true}, clean, 5).key, spokenLine({completed: true, counted: true, accepted: true}, clean, 6).key);
  for (const outcome of [{completed: true, counted: true, accepted: true}, {issue: 'tracking'}, {issue: 'tempo'}, {issue: 'range'}])
    for (const lang of ['en', 'ar']) {
      const line = spokenLine(outcome, clean, 7, lang);
      assert.ok(line.text.split(' ').length <= 5, line.text);
      assert.ok(!/\d/.test(line.text), line.text);
    }
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

test('the default timer works where browser timers reject a foreign "this"', () => {
  const original = globalThis.setTimeout;
  globalThis.setTimeout = function (f, ms) { if (this !== undefined && this !== globalThis) throw new TypeError('Illegal invocation'); return 1; };
  try {
    const synth = {speaking: false, cancel() {}, speak() {}, getVoices: () => [{name: 'Basic', lang: 'en-US'}]};
    const coach = new SpeechCoach({synth, Utterance: class { constructor(t) { this.text = t; } }, now: () => 1});
    assert.equal(coach.say('Good form.'), true);
  } finally { globalThis.setTimeout = original; }
});
