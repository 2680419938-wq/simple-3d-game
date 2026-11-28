// 割草 roguelite 的等级 / 技能槽 / 升级抽卡。纯数据层，不 import three，方便 node 直接测。
export const SLOTS = 4;

/** 技能池：demo 的全部十个。起手一个都没有，靠升级卡抽。 */
export const SKILL_META = {
  ice:         { name: '冰枪',   desc: '沿朝向一条冰线，穿过的全部命中' },
  thunder:     { name: '雷枪',   desc: '直线落雷，落点连锁电弧' },
  beam:        { name: '光柱',   desc: '持续光束，按 tick 反复伤害' },
  phoenix:     { name: '凤凰',   desc: '身前爆开，范围最大' },
  void:        { name: '虚空',   desc: '暗影光带横扫一条走廊' },
  singularity: { name: '奇点',   desc: '定点塌缩，持续吸附并反复伤害' },
  worldtree:   { name: '世界树', desc: '藤蔓从地面炸开，大范围多段' },
  snare:       { name: '电笼',   desc: '落点张起雷笼，笼内持续电击' },
  glacier:     { name: '冰川冠', desc: '地面拔起一圈冰晶墙，命中冻结' },
  meteor:      { name: '陨石',   desc: '抛射火球，落地爆炸（伤害最高）' },
};
export const POOL = Object.keys(SKILL_META);

/** 各技能的舒适施法距离（米）：瞬发近战型短，抛射/定点型中等，光柱射得远。 */
export const RANGE = {
  ice: 11, thunder: 12, beam: 13, phoenix: 6,
  void: 9, singularity: 8, worldtree: 6, snare: 7, glacier: 7, meteor: 10,
};

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

  /** 手动升一级（按键/调试用），不消耗经验。 */
  grantLevel() { this.xp = 0; this.level++; return 1; }

  /** 返回本次连升了几级（一次多杀可能连升）。 */
  addKill(n = 1) {
    this.xp += n;
    let ups = 0;
    while (this.xp >= this.need) { this.xp -= this.need; this.level++; ups++; }
    return ups;
  }

  damageMul(element) { return (this.dmg[element] ?? 1) * this.dmgAll; }
  cooldownMul(element) { return Math.max(CARD.minCooldown, (this.cd[element] ?? 1) * this.cdAll); }

  _shuffle(list) {
    for (let i = list.length - 1; i > 0; i--) {
      const j = Math.floor(this.rng() * (i + 1));
      const t = list[i]; list[i] = list[j]; list[j] = t;
    }
    return list;
  }

  /**
   * 抽 n 张互不相同的卡。
   * 有空槽 → 只出「解锁」，从没拥有的技能里随机取 n 个（所以第一次升级是十选三）。
   * 槽满   → 只出强化（伤害/冷却），且至少一张伤害，免得出三张废卡。
   */
  rollCards(n = 3) {
    if (this.freeSlot >= 0) {
      const avail = POOL.filter((el) => !this.has(el));
      return this._shuffle(avail.slice()).slice(0, n).map((el) => ({ kind: 'unlock', element: el }));
    }
    const pool = [];
    for (const s of this.slots) {
      pool.push({ kind: 'damage', element: s.element }, { kind: 'cooldown', element: s.element });
    }
    pool.push({ kind: 'damage', element: 'all' }, { kind: 'cooldown', element: 'all' });
    const picked = this._shuffle(pool).slice(0, n);
    if (picked.length && !picked.some((c) => c.kind === 'damage')) {
      const d = this._shuffle(pool.filter((c) => c.kind === 'damage'))[0];
      if (d) picked[picked.length - 1] = d;
    }
    return picked;
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
