import assert from 'node:assert/strict';
import test from 'node:test';
import {GAP_SECONDS, REPEAT_SECONDS, SpeechCoach} from '../../web/speech-coach.js';

function setup(voices = [{lang: 'en-US', localService: true}, {lang: 'ar-SA', localService: true}]) {
  const said = [];
  const synth = {speaking: false, cancelled: 0, cancel() { this.cancelled++; this.speaking = false; }, speak(u) { said.push(u); }, getVoices: () => voices};
  class Utterance { constructor(text) { this.text = text; } }
  const clock = {t: 100};
  return {coach: new SpeechCoach({synth, Utterance, now: () => clock.t}), said, synth, clock};
}

test('a comment is spoken once, then again only after the repeat gap', () => {
  const {coach, said, clock} = setup();
  assert.equal(coach.say('Keep your knee in line'), true);
  clock.t += GAP_SECONDS + 1;
  assert.equal(coach.say('Keep your knee in line'), false);
  clock.t = 100 + REPEAT_SECONDS + 1;
  assert.equal(coach.say('Keep your knee in line'), true);
  assert.equal(said.length, 2);
});

test('calm comments never queue while speech is playing', () => {
  const {coach, said, synth, clock} = setup();
  coach.say('First');
  synth.speaking = true;
  clock.t += GAP_SECONDS + 1;
  assert.equal(coach.say('Second'), false);
  assert.equal(said.length, 1);
});

test('a warning interrupts a calmer comment', () => {
  const {coach, said, synth, clock} = setup();
  coach.say('Keep going');
  synth.speaking = true;
  clock.t += 2;
  assert.equal(coach.say('Pause and reset', {urgent: true}), true);
  assert.equal(synth.cancelled, 1);
  assert.equal(said.at(-1).text, 'Pause and reset');
});

test('Arabic text uses an Arabic voice and is skipped when the device has none', () => {
  const withVoice = setup();
  assert.equal(withVoice.coach.say('راجع حركتك'), true);
  assert.equal(withVoice.said[0].lang, 'ar-SA');
  const without = setup([{lang: 'en-US', localService: true}]);
  assert.equal(without.coach.say('راجع حركتك'), false);
  assert.equal(without.coach.missing('ar'), true);
  assert.equal(without.said.length, 0);
});

test('an empty voice list is not treated as a missing language', () => {
  assert.equal(setup([]).coach.missing('ar'), false);
});

test('muted speech stays silent', () => {
  const {coach, said} = setup();
  coach.enabled = false;
  assert.equal(coach.say('Keep going'), false);
  assert.equal(said.length, 0);
});

test('browsers without speech do nothing and do not throw', () => {
  const coach = new SpeechCoach({synth: undefined, Utterance: undefined, now: () => 1});
  assert.equal(coach.supported, false);
  assert.equal(coach.say('Keep going'), false);
  assert.equal(coach.unlock(), false);
  coach.stop();
});
