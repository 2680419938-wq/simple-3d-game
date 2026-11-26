// 敌人：Zombiegirl 蒙皮网格（AnimLib/zombiegirl_build.py 烘的 GLB）＋ 5 条 Mixamo 僵尸动作。
// 烘的时候就按 24 fps 把动作烤进了同一套 mixamorig 骨架上，网页端不需要任何重定向。
// GLB 加载失败则退回旧路：没有蒙皮的 FBX 骨架 + 挂在骨骼上的基本体占位体格。
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { clone as cloneSkinned } from 'three/addons/utils/SkeletonUtils.js';

const SRC = {
  idle: '/models/zombie/idle.fbx',
  walk: '/models/zombie/walk.fbx',
  run: '/models/zombie/run.fbx',
  attack: '/models/zombie/attack.fbx',
  death: '/models/zombie/death.fbx',
};

const CM = 0.01;   // 裸 FBX 骨架以厘米为单位（髋高 92.5）；烘好的 GLB 已经烘进 0.01，缩放取 1

// 烘出来的走路/跑步片段带着 Mixamo 的根位移：髋部一个周期前移 1.28 m（走）/ 2.30 m（跑），
// 播到最后一帧会瞬移回起点。这里按线性斜坡把净位移扣掉（左右摆动与上下起伏都留着），
// 顺便返回片段自己的设计地速（m/s），用来把播放速率和移动速度对齐——否则脚下一直在打滑。
export function stripRootDrift(clip, unit) {
  const tr = clip.tracks.find((t) => /mixamorig:?Hips.position$/.test(t.name));
  if (!tr) return 0;
  const v = tr.values, n = v.length / 3;
  if (n < 2) return 0;
  const dx = v[(n - 1) * 3] - v[0];
  const dy = v[(n - 1) * 3 + 1] - v[1];
  const dz = v[(n - 1) * 3 + 2] - v[2];
  for (let i = 0; i < n; i++) {
    const k = i / (n - 1);
    v[i * 3] -= dx * k;
    v[i * 3 + 1] -= dy * k;
    v[i * 3 + 2] -= dz * k;
  }
  return (Math.hypot(dx, dz) * unit) / clip.duration;
}
const GLB = '/models/zombie/zombiegirl.glb';

export const ENEMY = {
  hp: 30,
  walkSpeed: 0.90,   // 片段本身的设计地速是 0.31 m/s（走）/ 2.75 m/s（跑），播放速率按这个比例对齐
  runSpeed: 3.0,
  sight: 15,
  reach: 1.9,        // 攻击判定距离（米）
  dmg: 12,
  attackCD: 1.6,
  attackRate: 2.0,   // 攻击片段 2.62 s 太长，2× 播到 1.31 s
  radius: 0.45,
};

const SKIN = 0x8b9770;
const CLOTH = 0x4a4d45;
const NAIL = 0xd9d3bd;

function std(color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.86, metalness: 0.0, ...opts });
}

// 取骨骼到第一个子骨骼的局部向量（厘米），盒子沿它摆放，这样不依赖骨骼的局部轴约定
function segLocal(bone) {
  if (!bone) return null;
  const child = bone.children.find((c) => c.isBone);
  if (!child) return null;
  const v = child.position.clone();
  return v.length() < 1e-3 ? null : v;
}

function segBox(bone, w, d, m) {
  const v = segLocal(bone);
  if (!v) return null;
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, v.length() * 1.04, d), m);
  mesh.position.copy(v).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v.clone().normalize());
  return mesh;
}

function attach(proto, name, build) {
  const bone = proto.getObjectByName(name);
  const mesh = bone && build(bone);
  if (mesh) bone.add(mesh);
  return !!mesh;
}

// 占位体格：躯干/四肢用盒子套在骨骼段上，头是球，手上有爪，眼睛自发光
export function buildPuppet(proto) {
  proto.updateMatrixWorld(true);
  const skin = std(SKIN);
  const cloth = std(CLOTH);
  const nail = std(NAIL, { roughness: 0.45 });
  let n = 0;
  const add = (name, m) => { if (!m) return; const b = proto.getObjectByName(name); if (b) { b.add(m); n++; } };

  // 躯干（由下往上略加宽）
  add('mixamorigHips', segBox(proto.getObjectByName('mixamorigHips'), 26, 18, cloth));
  add('mixamorigSpine', segBox(proto.getObjectByName('mixamorigSpine'), 27, 18, cloth));
  add('mixamorigSpine1', segBox(proto.getObjectByName('mixamorigSpine1'), 31, 19, cloth));
  add('mixamorigSpine2', segBox(proto.getObjectByName('mixamorigSpine2'), 34, 20, cloth));
  add('mixamorigNeck', segBox(proto.getObjectByName('mixamorigNeck'), 11, 11, skin));

  // 头
  attach(proto, 'mixamorigHead', (b) => {
    const v = segLocal(b);
    const len = v ? v.length() : 14;
    const head = new THREE.Mesh(new THREE.SphereGeometry(len * 0.78, 16, 12), skin);
    head.scale.set(1, 1.12, 1.06);
    head.position.copy(v || new THREE.Vector3(0, 7, 0)).multiplyScalar(0.5);
    // 眼：头骨局部 +Y 朝向头顶、+Z 为脸朝方向，两只分列两侧
    const eyeM = std(0x1a0a06, { emissive: 0xff3a12, emissiveIntensity: 2.2, roughness: 0.4 });
    for (const sx of [-1, 1]) {
      const eye = new THREE.Mesh(new THREE.SphereGeometry(2.1, 8, 6), eyeM);
      eye.position.set(sx * len * 0.34, head.position.y + len * 0.08, len * 0.62);
      head.add(eye);
    }
    return head;
  });

  // 手臂 + 爪
  for (const s of ['Left', 'Right']) {
    add('mixamorig' + s + 'Arm', segBox(proto.getObjectByName('mixamorig' + s + 'Arm'), 9.5, 9.5, skin));
    add('mixamorig' + s + 'ForeArm', segBox(proto.getObjectByName('mixamorig' + s + 'ForeArm'), 8.5, 8.5, skin));
    attach(proto, 'mixamorig' + s + 'Hand', (b) => {
      const v = segLocal(b);
      const g = new THREE.Group();
      if (v) {
        const palm = new THREE.Mesh(new THREE.BoxGeometry(7, v.length() * 1.6, 9), skin);
        palm.position.copy(v).multiplyScalar(0.5);
        g.add(palm);
        for (let i = 0; i < 3; i++) {
          const claw = new THREE.Mesh(new THREE.ConeGeometry(1.5, 7, 6), nail);
          claw.position.copy(v).multiplyScalar(0.9);
          claw.position.x += (i - 1) * 2.4;
          claw.position.z += 1.5;
          claw.rotation.x = Math.PI * 0.5;   // 锥体默认朝 +Y，转成朝前
          g.add(claw);
        }
      }
      return g.children.length ? g : null;
    });
  }

  // 腿 + 脚
  for (const s of ['Left', 'Right']) {
    add('mixamorig' + s + 'UpLeg', segBox(proto.getObjectByName('mixamorig' + s + 'UpLeg'), 13, 13, cloth));
    add('mixamorig' + s + 'Leg', segBox(proto.getObjectByName('mixamorig' + s + 'Leg'), 11, 11, cloth));
    add('mixamorig' + s + 'Foot', segBox(proto.getObjectByName('mixamorig' + s + 'Foot'), 10, 12, skin));
  }
  return n;
}

function clipOf(obj, name) {
  const c = obj.animations && obj.animations[0];
  if (!c) return null;
  const out = c.clone();
  out.name = name;
  return out;
}

// 烘好的 GLB：{ proto: 蒙皮网格根节点, clips: {idle,walk,run,attack,death}, scale: 1 }
async function loadGlb() {
  const gltf = await new Promise((res, rej) => new GLTFLoader().load(GLB, res, undefined, rej));
  const clips = {};
  for (const c of gltf.animations) clips[c.name] = c;
  for (const k in SRC) if (!clips[k]) throw new Error('glb missing clip ' + k);
  gltf.scene.updateMatrixWorld(true);
  // 轨道单位是厘米（髋局部平移 -107.59）；死亡片段的下坠是动作本身，不剥
  const clipSpeed = { walk: stripRootDrift(clips.walk, CM), run: stripRootDrift(clips.run, CM) };
  return { proto: gltf.scene, clips, clipSpeed, scale: 1 };
}

export async function loadEnemyAssets() {
  try {
    return await loadGlb();
  } catch (err) {
    console.warn('[enemy] GLB 加载失败，退回占位体格', err);
  }
  const loader = new FBXLoader();
  const one = (url) => new Promise((res, rej) => loader.load(url, res, undefined, rej));
  const [idle, walk, run, attack, death] = await Promise.all(Object.values(SRC).map(one));
  buildPuppet(idle);
  idle.updateMatrixWorld(true);
  const clips = {
    idle: clipOf(idle, 'Idle'),
    walk: clipOf(walk, 'Walk'),
    run: clipOf(run, 'Run'),
    attack: clipOf(attack, 'Attack'),
    death: clipOf(death, 'Death'),
  };
  const clipSpeed = { walk: stripRootDrift(clips.walk, CM), run: stripRootDrift(clips.run, CM) };
  return { proto: idle, clips, clipSpeed, scale: CM };
}

const _wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));

export class Enemy {
  constructor(assets, opts) {
    this.root = cloneSkinned(assets.proto);
    this.root.scale.setScalar(assets.scale ?? CM);
    this.root.position.set(opts.x, opts.y || 0, opts.z);
    this.root.traverse((o) => {
      if (!o.isMesh) return;
      o.castShadow = true;
      o.receiveShadow = false;
      o.frustumCulled = false;
      o.material = o.material.clone();          // 受击闪红要逐只独立
      o.userData.baseEmissive = o.material.emissive ? o.material.emissive.clone() : null;
    });
    this.mixer = new THREE.AnimationMixer(this.root);
    this.clipSpeed = assets.clipSpeed || {};
    this.actions = {};
    for (const k in assets.clips) {
      const c = assets.clips[k];
      if (!c) continue;
      const a = this.mixer.clipAction(c);
      if (k === 'attack' || k === 'death') { a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true; }
      this.actions[k] = a;
    }
    this.cur = null;
    this.hp = ENEMY.hp;
    this.state = 'idle';
    this.gait = 'walk';
    this.cd = 0;
    this.atkT = 0;
    this.hitDone = false;
    this.pendingHit = false;
    this.stun = 0;
    this.deadT = 0;
    this.flash = 0;
    this.kb = new THREE.Vector3();
    this.play('idle', 0);
  }

  play(name, fade = 0.25, rate = 1, warp = false) {
    const a = this.actions[name];
    if (!a) return;
    const once = name === 'attack' || name === 'death';
    if (this.cur === name) {
      a.setEffectiveTimeScale(rate);
      // LoopOnce 播完是 paused + 定格在末帧：重播不 reset 就整只僵尸再也不动（曾「打两下就僵住」）
      if (once && !a.isRunning()) {
        a.reset();
        a.enabled = true;
        a.setEffectiveWeight(1);
        a.play();
        a.setEffectiveTimeScale(rate);
      }
      return;
    }
    const from = this.actions[this.cur];
    a.reset();
    a.enabled = true;
    a.setEffectiveTimeScale(rate);
    a.setEffectiveWeight(1);
    a.play();
    if (from && from !== a) from.crossFadeTo(a, fade, warp);
    this.cur = name;
  }

  setFlash(v) {
    this.root.traverse((o) => {
      if (!o.isMesh || !o.material || !o.material.emissive) return;
      const base = o.userData.baseEmissive || new THREE.Color(0, 0, 0);
      o.material.emissive.setRGB(base.r + 0.34 * v, base.g + 0.05 * v, base.b + 0.02 * v);   // 真贴图下 0.7 会整只过曝成橙色
      o.material.emissiveIntensity = 1 + 0.8 * v;
    });
  }

  get alive() { return this.state !== 'dead'; }

  hurt(dmg, dir) {
    if (!this.alive) return false;
    this.hp -= dmg;
    this.flash = 1;
    this.setFlash(1);
    this.kb.set(dir.x, 0, dir.z).multiplyScalar(3.4);
    if (this.hp <= 0) { this.die(); return true; }
    if (this.state === 'attack') { this.state = 'chase'; this.play('idle', 0.1); }   // 打断挥击时别留着定格姿势
    this.stun = 0.18;
    return false;
  }

  die() {
    this.state = 'dead';
    this.deadT = 0;
    this.kb.set(0, 0, 0);
    this.play('death', 0.12, 1.3);
  }

  consumeHit() {
    const h = this.pendingHit;
    this.pendingHit = false;
    return h;
  }

  update(dt, target, groundAt, resolve) {
    this.mixer.update(dt);
    if (this.flash > 0) { this.flash = Math.max(0, this.flash - dt * 6); this.setFlash(this.flash); }

    const p = this.root.position;
    if (!this.alive) {
      this.deadT += dt;
      if (this.deadT > 2.6) this.root.visible = false;
      return;
    }
    if (this.kb.lengthSq() > 1e-4) {
      p.addScaledVector(this.kb, dt);
      this.kb.multiplyScalar(1 - Math.min(1, dt * 9));
    }

    const dx = target.x - p.x;
    const dz = target.z - p.z;
    const dist = Math.hypot(dx, dz) || 1e-4;
    this.cd = Math.max(0, this.cd - dt);

    // 朝向：模型自身朝 +Z
    const yaw = Math.atan2(dx, dz);
    this.root.rotation.y += _wrap(yaw - this.root.rotation.y) * Math.min(1, dt * 7);

    if (this.stun > 0) { this.stun -= dt; }
    else if (this.state === 'attack') {
      this.atkT += dt;
      const dur = this.actions.attack.getClip().duration / ENEMY.attackRate;
      if (!this.hitDone && this.atkT >= dur * 0.45) { this.hitDone = true; this.pendingHit = true; }
      if (this.atkT >= dur) { this.state = 'chase'; }
    } else {
      const seen = dist < ENEMY.sight;
      const walking = this.cur === 'walk' || this.cur === 'run';
      // 已在走就多走到 1.43 m 才停，否则站在 1.71 m 线上会 idle/walk 逐帧互切、每切一次就 reset 片段
      const nearLine = ENEMY.reach * (walking ? 0.75 : 0.9);
      if (seen && dist <= ENEMY.reach && this.cd <= 0) {
        this.state = 'attack';
        this.atkT = 0;
        this.hitDone = false;
        this.cd = ENEMY.attackCD;
        this.play('attack', 0.12, ENEMY.attackRate);
      } else if (seen && dist > nearLine) {
        // 走/跑之间留 1.5 m 滞回带：正好卡在 6 m 边界上会逐帧来回切，每次都 reset 片段（看起来像走路不断重启）
        if (dist > 7) this.gait = 'run';
        else if (dist < 5.5) this.gait = 'walk';
        const sp = this.gait === 'run' ? ENEMY.runSpeed : ENEMY.walkSpeed;
        p.x += (dx / dist) * sp * dt;
        p.z += (dz / dist) * sp * dt;
        const rate = this.clipSpeed[this.gait] ? sp / this.clipSpeed[this.gait] : 1;
        this.play(this.gait, 0.28, rate);   // 不用 warp：它会在淡入结束把 timeScale 覆回 1，脚下又开始滑
        this.state = 'chase';
      } else if (seen) {
        // 已经贴到攻击距离、只是还在冷却：站定等下一刀，别留着上一刀 LoopOnce 定格的姿势
        this.play('idle', 0.2);
        this.state = 'chase';
      } else if (this.state === 'chase') {
        this.state = 'idle';
        this.play('idle', 0.3);
      }
    }

    if (resolve) resolve(p, ENEMY.radius, p.y);
    if (groundAt) p.y = groundAt(p.x, p.z, p.y);
  }

  dispose() {
    this.mixer.stopAllAction();
    this.root.traverse((o) => { if (o.isMesh) { o.geometry.dispose(); o.material.dispose(); } });
    if (this.root.parent) this.root.parent.remove(this.root);
  }
}
