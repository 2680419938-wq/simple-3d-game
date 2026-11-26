import { Progression, SLOTS, POOL, needFor, cardText, CARD } from '../src/progression.js';

let pass = 0, fail = 0;
const ok = (name, cond, extra = '') => {
  if (cond) { pass++; console.log('PASS ' + name); }
  else { fail++; console.log('FAIL ' + name + (extra ? ' — ' + extra : '')); }
};

// 固定随机序列，保证抽卡可复现
let seed = 12345;
const rng = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);

const p = new Progression(rng);
ok('starts at level 1 with 4 empty slots', p.level === 1 && p.slots.length === SLOTS && p.freeSlot === 0);
ok('need grows with level', needFor(1) === 8 && needFor(3) === 12);

// 升级：只按击杀推进，余量保留
const ups = p.addKill(20);
ok('addKill returns level-ups and keeps remainder', ups === 2 && p.level === 3 && p.xp === 2, 'ups=' + ups + ' lv=' + p.level + ' xp=' + p.xp);

// 抽卡：有空槽时必给解锁
const first = p.rollCards(3);
ok('rolls 3 distinct cards', first.length === 3 && new Set(first.map((c) => c.kind + ':' + c.element)).size === 3);
ok('empty slot forces an unlock card', first.some((c) => c.kind === 'unlock'));
const unlock = first.find((c) => c.kind === 'unlock');
ok('unlock card applies to first free slot', p.apply(unlock) === true && p.slots[0].element === unlock.element);
ok('pool excludes owned element', p.rollCards(5).every((c) => c.kind !== 'unlock' || c.element !== unlock.element));

// 填满全部槽位后不再出解锁卡，且至少一张伤害
for (const el of POOL) if (!p.has(el)) p.unlock(el);
ok('all slots filled', p.freeSlot === -1 && p.owned.length === SLOTS);
const full = p.rollCards(3);
ok('full slots: no unlock cards', full.every((c) => c.kind !== 'unlock'));
ok('full slots: at least one damage card', full.some((c) => c.kind === 'damage'));

// 伤害与冷却乘子
const before = p.damageMul('ice');
p.apply({ kind: 'damage', element: 'ice' });
ok('damage card stacks per element', Math.abs(p.damageMul('ice') - before * (1 + CARD.damage)) < 1e-9);
p.apply({ kind: 'damage', element: 'all' });
ok('global damage card multiplies every element', Math.abs(p.damageMul('thunder') - (1 + CARD.damageAll)) < 1e-9);
p.apply({ kind: 'cooldown', element: 'ice' });
ok('cooldown card lowers the multiplier', p.cooldownMul('ice') < 1 && p.cooldownMul('ice') > CARD.minCooldown - 1e-9);
for (let i = 0; i < 40; i++) p.apply({ kind: 'cooldown', element: 'ice' });
ok('cooldown multiplier floors', Math.abs(p.cooldownMul('ice') - CARD.minCooldown) < 1e-9, 'got ' + p.cooldownMul('ice'));
ok('other elements untouched by ice cooldown cards', p.cooldownMul('beam') === 1);

// 卡面文案
ok('card text has title and desc', cardText({ kind: 'unlock', element: 'beam' }).title.includes('光柱') && cardText({ kind: 'damage', element: 'all' }).desc.includes('12%'));
ok('unknown card is rejected', p.apply({ kind: 'nope' }) === false && p.apply(null) === false);

console.log(pass + ' PASS, ' + fail + ' FAIL');
process.exit(fail ? 1 : 0);
