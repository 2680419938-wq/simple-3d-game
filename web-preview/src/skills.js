// 技能系统：把 ThreeJSVFX-Demo 的 10 个技能接进本项目（MIT © 2026 mohamedachrefelouafi）。
// 适配层只做两件事：装配 demo ability 需要的共享服务上下文，以及把命中结算换成本项目的僵尸。
import * as THREE from 'three';
import { ParticleEngine } from './fx/particles/ParticleEngine.js';
import { LightPool } from './fx/effects/LightPool.js';
import { DecalSystem } from './fx/effects/GroundDecals.js';
import { FissureSystem } from './fx/effects/GroundFissures.js';
import { BurstSystem } from './fx/effects/BurstSphere.js';
import { CameraShake } from './fx/effects/CameraShake.js';
import { ScreenFlash } from './fx/effects/ScreenFlash.js';
import { AbilityManager } from './fx/abilities/AbilityManager.js';
import { ABILITY_PROFILES } from './fx/gameplay/abilityProfiles.js';
import { frame } from './fx/core/FrameUniforms.js';
import { settings } from './fx/config/settings.js';

/** 森林用 FogExp2，24 m 处的特效会被雾洗成白色；demo 场景没有雾，所以特效材质一律关雾。 */
function noFog(root) {
  root.traverse((o) => {
    const m = o.material;
    if (!m) return;
    for (const mm of (Array.isArray(m) ? m : [m])) {
      if (mm.fog !== false) { mm.fog = false; mm.needsUpdate = true; }
    }
  });
}

const _end = new THREE.Vector3();
const _dir = new THREE.Vector3();

/**
 * demo 的 CombatSystem 结算它自己的 EnemyManager；这里换成我们的僵尸列表，
 * 只保留「命中查询 + 扣血」。
 */
class Combat {
  constructor(getEnemies, radiusOf, onHit) {
    this.getEnemies = getEnemies;
    this.radiusOf = radiusOf;
    this.onHit = onHit;
    this.elapsed = 0;
    this.nextCastId = 1;
    this.damageScale = 1;
    this.dmgMul = {};      // element -> 该次施放吃的伤害乘子（升级卡）
  }

  beginCast(ability) {
    ability.gameplay = { castId: this.nextCastId++, tick: -1, impacted: false, startedAt: this.elapsed };
  }

  onAbilityImpact(ability) {
    const profile = ABILITY_PROFILES[ability.element];
    const state = ability.gameplay;
    if (!profile || !state || state.impacted) return;
    state.impacted = true;
    state.impactAt = this.elapsed;
    state.tick = -1;
    if (profile.mode.startsWith('impact-')) this._apply(ability, profile, 0);
  }

  updateAbility(ability) {
    const profile = ABILITY_PROFILES[ability.element];
    const state = ability.gameplay;
    if (!profile || !state || !profile.mode.startsWith('tick-') || !state.impacted) return;
    const age = Math.max(0, this.elapsed - (state.impactAt ?? state.startedAt));
    const tick = Math.floor(age / profile.interval);
    if (tick === state.tick || age > profile.duration) return;
    state.tick = tick;
    this._apply(ability, profile, tick);
  }

  endCast(ability) { ability.gameplay = null; }

  _radius(ability, profile, directKey, keyName, fallback) {
    if (profile[directKey] !== undefined) return profile[directKey];
    const key = profile[keyName];
    return key ? (settings[ability.element]?.[key] ?? fallback) : fallback;
  }

  _apply(ability, profile, tick) {
    const state = ability.gameplay;
    if (!state) return;
    ability.pointAt(1, _end).setY(0);
    let hits;
    if (profile.mode.endsWith('sphere')) {
      hits = this._sphere(_end, this._radius(ability, profile, 'radius', 'radiusKey', 1));
    } else {
      hits = this._line(ability.origin, _end,
        this._radius(ability, profile, 'startRadius', 'startRadiusKey', 0.5),
        this._radius(ability, profile, 'endRadius', 'endRadiusKey', 0.5));
    }
    const dmg = profile.damage * this.damageScale * (this.dmgMul[ability.element] ?? 1);
    for (const e of hits) {
      if (profile.radial) _dir.subVectors(e.root.position, _end).setY(0);
      else _dir.copy(ability.direction).setY(0);
      if (_dir.lengthSq() < 1e-6) _dir.set(1, 0, 0); else _dir.normalize();
      const killed = e.hurt(dmg, { x: _dir.x, z: _dir.z });
      this.onHit?.(e, killed, ability.element, dmg);
    }
  }

  _sphere(center, radius) {
    const out = [];
    const r = radius + this.radiusOf;
    for (const e of this.getEnemies()) {
      if (!e.alive) continue;
      const p = e.root.position;
      if (Math.hypot(p.x - center.x, p.z - center.z) <= r) out.push(e);
    }
    return out;
  }

  _line(a, b, r0, r1) {
    const out = [];
    const abx = b.x - a.x, abz = b.z - a.z;
    const len2 = abx * abx + abz * abz || 1e-6;
    for (const e of this.getEnemies()) {
      if (!e.alive) continue;
      const p = e.root.position;
      let t = ((p.x - a.x) * abx + (p.z - a.z) * abz) / len2;
      t = t < 0 ? 0 : t > 1 ? 1 : t;
      const cx = a.x + abx * t, cz = a.z + abz * t;
      if (Math.hypot(p.x - cx, p.z - cz) <= r0 + (r1 - r0) * t + this.radiusOf) out.push(e);
    }
    return out;
  }
}

export function createSkills({ scene, camera, getEnemies, radiusOf = 0.5, onHit = null }) {
  // 所有特效材质的软边都靠 softFade(frame.uSceneDepth, ...) 裁掉与地面的穿插；
  // 本项目还没有打包深度 prepass，先用一张「远平面」占位贴图让软边恒等于 1（= 不裁），
  // 否则 unpackRGBAToDepth(0) 会把每个像素判成被遮挡，整片特效应 alpha=0 而隐形。
  if (!frame.uSceneDepth.value) {
    // (255,0,0,0) 解包出来正好是深度 1.0；给 1.0 以上的值会让 perspectiveDepthToViewZ 翻成正数，软边反而恒为 0。
    const far = new THREE.DataTexture(new Uint8Array([255, 0, 0, 0]), 1, 1, THREE.RGBAFormat);
    far.needsUpdate = true;
    frame.uSceneDepth.value = far;
  }
  const particles = new ParticleEngine(scene);
  const lights = new LightPool(scene);
  const decals = new DecalSystem(scene);
  const fissures = new FissureSystem(scene);
  const bursts = new BurstSystem(scene);
  const shakeRig = { camera, shakeOffset: new THREE.Vector3(), shakeRoll: 0 };
  const shake = new CameraShake(shakeRig);
  const flash = new ScreenFlash();
  // demo 的 Environment 只是替材质串起 onBeforeCompile；本项目等价于就地链式挂补丁。
  // customProgramCacheKey 必须每个材质唯一，否则 three 会把不同补丁当成同一程序复用。
  let patchSeq = 0;
  const environment = {
    registerShadowCasterWithPatch(material, patch) {
      const previous = material.onBeforeCompile;
      material.onBeforeCompile = function (shader, renderer) {
        if (previous) previous.call(this, shader, renderer);
        patch.call(this, shader, renderer);
      };
      const key = 'vfxp' + (++patchSeq);
      material.customProgramCacheKey = () => key;
      material.needsUpdate = true;
      return material;
    },
  };
  const combat = new Combat(getEnemies, radiusOf, onHit);
  const manager = new AbilityManager({
    scene, camera, environment, particles, lights, decals, fissures, bursts, shake, flash, combat,
  });

  const cooldowns = new Map();
  const cooling = (element) => cooldowns.get(element) ?? 0;

  return {
    manager, combat, flash, shake, shakeRig, particles, decals, bursts, fissures, lights,
    setSunDir(d) { frame.uLightDir.value.copy(d).normalize(); },
    resize(w, h) { frame.uResolution.value.set(w, h); },
    cooling,
    setDamageMul(element, mul) { combat.dmgMul[element] = mul; },
    cast(element, origin, direction, distance = 12, cdMul = 1) {
      if (cooling(element) > 0) return null;
      cooldowns.set(element, (settings[element]?.cooldown ?? 2) * cdMul);
      const ability = manager.cast(origin, direction, distance, element);
      if (ability) noFog(ability.group);
      return ability;
    },
    hud(elements = ['ice', 'thunder']) {
      return elements
        .map((e) => e + (cooling(e) > 0 ? ' ' + cooling(e).toFixed(1) + 's' : ' 就绪'))
        .join(' · ');
    },
    update(dt) {
      frame.uTime.value += dt;
      frame.uDelta.value = dt;
      combat.elapsed += dt;
      for (const [k, v] of cooldowns) if (v > 0) cooldowns.set(k, Math.max(0, v - dt));
      manager.update(dt);
      particles.flush();
      decals.update(dt);
      bursts.update(dt);
      fissures.update(dt);
      lights.update(dt);
      shake.update(dt);
      flash.update(dt);
    },
  };
}
