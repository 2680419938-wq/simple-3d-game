// 割草 roguelite 的等级 / 技能槽 / 升级抽卡。纯数据层，不 import three，方便 node 直接测。
export const SLOTS = 4;

/** 技能池：只放实测在本项目里能正常渲染的四个（snare/glacier/meteor 缺主体几何，void 只有一条光带）。 */
export const SKILL_META = {
  ice: { name: '冰枪', desc: '沿朝向一条冰线，穿过的全部命中' },
  thunder: { name: '雷枪', desc: '直线落雷，落点连锁电弧' },
  beam: { name: '光柱', desc: '持续光束，按 tick 反复伤害' },
  phoenix: { name: '凤凰', desc: '身前爆开，范围最大' },
};
export const POOL = Object.keys(SKILL_META);

export const CARD = {
  damage: 0.25,          // 单技能：每张 +25%
  cooldown: 0.85,        // 单技能：每张 ×0.85
  damageAll: 0.12,
  cooldownAll: 0.90,
  minCooldown: 0.35,     // 冷却乘子的下限，避免叠到 0
};

/** 升到下一级需要的击杀数：8、10、12 … */
export function needFor(level) {
  return 6 + level * 2;
}

export function cardText(card) {
  const m = SKILL_META[card.element];
  if (card.kind === 'unlock') return { title: '解锁 ' + m.name, desc: '占一个空槽　' + m.desc };
  if (card.kind === 'damage') {
    return card.element === 'all'
      ? { title: '全能强化', desc: '所有技能伤害 +' + Math.round(CARD.damageAll * 100) + '%' }
      : { title: m.name + ' · 强化', desc: '该技能伤害 +' + Math.round(CARD.damage * 100) + '%' };
  }
  return card.element === 'all'
    ? { title: '急速冷却', desc: '所有技能冷却 −' + Math.round((1 - CARD.cooldownAll) * 100) + '%' }
    : { title: m.name + ' · 急速', desc: '该技能冷却 −' + Math.round((1 - CARD.cooldown) * 100) + '%' };
}

export class Progression {
  constructor(rng = Math.random) {
    this.rng = rng;
    this.level = 1;
    this.xp = 0;
    this.slots = new Array(SLOTS).fill(null);
    this.dmg = {};     // element -> 伤害乘子
    this.cd = {};      // element -> 冷却乘子
    this.dmgAll = 1;
    this.cdAll = 1;
  }

  reset() {
    this.level = 1;
    this.xp = 0;
    this.slots.fill(null);
    this.dmg = {};
    this.cd = {};
    this.dmgAll = 1;
    this.cdAll = 1;
  }

  get need() { return needFor(this.level); }
  get owned() { return this.slots.filter(Boolean); }
  get freeSlot() { return this.slots.indexOf(null); }
  has(element) { return this.slots.some((s) => s && s.element === element); }

  unlock(element) {
    const i = this.freeSlot;
    if (i < 0 || this.has(element) || !SKILL_META[element]) return false;
    this.slots[i] = { element };
    return true;
  }

  /** 返回本次连升了几级（一次多杀可能连升）。 */
  addKill(n = 1) {
    this.xp += n;
    let ups = 0;
    while (this.xp >= this.need) { this.xp -= this.need; this.level++; ups++; }
    return ups;
  }

  damageMul(element) { return (this.dmg[element] ?? 1) * this.dmgAll; }
  cooldownMul(element) { return Math.max(CARD.minCooldown, (this.cd[element] ?? 1) * this.cdAll); }

  _candidates() {
    const out = [];
    const free = this.freeSlot >= 0;
    for (const el of POOL) {
      if (free && !this.has(el)) out.push({ kind: 'unlock', element: el });
      if (this.has(el)) {
        out.push({ kind: 'damage', element: el });
        out.push({ kind: 'cooldown', element: el });
      }
    }
    out.push({ kind: 'damage', element: 'all' });
    out.push({ kind: 'cooldown', element: 'all' });
    return out;
  }

  _shuffle(list) {
    for (let i = list.length - 1; i > 0; i--) {
      const j = Math.floor(this.rng() * (i + 1));
      const t = list[i]; list[i] = list[j]; list[j] = t;
    }
    return list;
  }

  /** 抽 n 张互不相同的卡；有空槽时保证至少一张解锁，满槽后保证至少一张伤害。 */
  rollCards(n = 3) {
    const pool = this._shuffle(this._candidates());
    const picked = [];
    const take = (c) => {
      if (picked.length >= n) return;
      if (picked.some((p) => p.kind === c.kind && p.element === c.element)) return;
      picked.push(c);
    };
    if (this.freeSlot >= 0) {
      const unlocks = pool.filter((c) => c.kind === 'unlock');
      if (unlocks.length) take(unlocks[0]);
    }
    for (const c of pool) take(c);
    if (this.freeSlot < 0 && !picked.some((c) => c.kind === 'damage')) {
      const d = pool.find((c) => c.kind === 'damage' && !picked.includes(c));
      if (d) picked[picked.length - 1] = d;
    }
    return picked.slice(0, n);
  }

  apply(card) {
    if (!card) return false;
    if (card.kind === 'unlock') return this.unlock(card.element);
    if (card.kind === 'damage') {
      if (card.element === 'all') this.dmgAll *= 1 + CARD.damageAll;
      else this.dmg[card.element] = (this.dmg[card.element] ?? 1) * (1 + CARD.damage);
      return true;
    }
    if (card.kind === 'cooldown') {
      if (card.element === 'all') this.cdAll *= CARD.cooldownAll;
      else this.cd[card.element] = (this.cd[card.element] ?? 1) * CARD.cooldown;
      return true;
    }
    return false;
  }
}
