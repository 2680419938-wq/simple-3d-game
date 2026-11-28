import { SOUNDS, VOICES, ALIAS, castSound, impactSound, attenuation, panFor } from '../src/audio.js';
import { POOL } from '../src/progression.js';

let pass = 0, fail = 0;
const ok = (n, c, extra = '') => { if (c) { pass++; console.log('PASS ' + n); } else { fail++; console.log('FAIL ' + n + (extra ? ' — ' + extra : '')); } };

ok('every sound has a duration', Object.values(SOUNDS).every((s) => s.dur > 0 && s.gain > 0));
ok('gain stays below 1', Object.values(SOUNDS).every((s) => s.gain <= 0.7));
ok('all ten pool elements have cast and impact sounds',
  POOL.length === 10 && POOL.every((el) => SOUNDS[castSound(el)] && SOUNDS[impactSound(el)]));
ok('aliased elements borrow a family sound', ALIAS.snare === 'thunder' && castSound('snare') === 'cast_thunder' && impactSound('glacier') === 'impact_ice' && castSound('meteor') === 'cast_phoenix');
ok('three new elements have their own voices', ['void', 'singularity', 'worldtree'].every((el) => !ALIAS[el] && SOUNDS['cast_' + el] && SOUNDS['impact_' + el]));
ok('unknown element falls back to swing', castSound('nope') === 'swing' && impactSound('nope') === 'hit');
ok('attenuation is 1 at 0 m', attenuation(0) === 1);
ok('attenuation decays with distance', attenuation(10) < attenuation(2) && attenuation(10) > 0.4, String(attenuation(10)));
ok('attenuation clamps negatives', attenuation(-5) === 1);
ok('pan centres at 0', panFor(0) === 0);
ok('pan clamps to +-1', panFor(50) === 1 && panFor(-50) === -1);
ok('pan is proportional', Math.abs(panFor(6) - 0.5) < 1e-9, String(panFor(6)));
ok('voice caps exist for the noisy sounds', VOICES.land > 0 && VOICES.die > 0);
console.log(pass + ' PASS, ' + fail + ' FAIL');
process.exit(fail ? 1 : 0);
