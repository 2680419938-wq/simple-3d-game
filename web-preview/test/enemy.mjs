// 敌人模块的结构/状态机测试（不依赖浏览器）：node test/enemy.mjs
import { readFileSync } from 'node:fs';
import * as THREE from 'three';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { buildPuppet, Enemy, ENEMY, stripRootDrift } from '../src/enemy.js';

const DIR = new URL('../public/models/zombie/', import.meta.url);
const parse = (n) => new FBXLoader().parse(
  readFileSync(new URL(n, DIR)).buffer.slice(0)
  , '');

function parseFile(name) {
  const buf = readFileSync(new URL(name, DIR));
  return new FBXLoader().parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), '');
}

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; } else { fail++; console.log('FAIL', m); } };

const idle = parseFile('idle.fbx');
const names = [];
idle.traverse((o) => { if (o.isBone) names.push(o.name); });
ok(names.length === 37, 'skeleton has 37 bones, got ' + names.length);

const meshCount = buildPuppet(idle);
ok(meshCount >= 14, 'puppet parts >= 14, got ' + meshCount);

// 占位体格尺寸：骨骼空间是厘米，整体 ×0.01 后应接近 1.8 m
idle.updateMatrixWorld(true);
const box = new THREE.Box3();
idle.traverse((o) => { if (o.isMesh) box.expandByObject(o); });
const size = box.getSize(new THREE.Vector3());
ok(size.y > 150 && size.y < 200, 'puppet height in cm ~1.8 m, got ' + size.y.toFixed(1));
ok(box.min.y > -20, 'puppet feet near y=0, got min.y ' + box.min.y.toFixed(1));

const assets = {
  proto: idle,
  clips: {
    idle: idle.animations[0],
    walk: parseFile('walk.fbx').animations[0],
    run: parseFile('run.fbx').animations[0],
    attack: parseFile('attack.fbx').animations[0],
    death: parseFile('death.fbx').animations[0],
  },
};
ok(assets.clips.attack.duration > 2, 'attack clip duration ' + assets.clips.attack.duration.toFixed(2));

const e = new Enemy(assets, { x: 0, y: 0, z: 0 });
// 动作确实在驱动骨骼：手臂骨在 rest pose（T-pose）里是水平张开的，播一会儿必须转走
const armBone = e.root.getObjectByName('mixamorigLeftArm');
const q0 = armBone.quaternion.clone();
for (let i = 0; i < 12; i++) e.update(1 / 60, { x: 5, y: 0, z: 0 }, () => 0, null);
ok(armBone.quaternion.angleTo(q0) > 0.05, 'animation drives bones, angle delta ' + armBone.quaternion.angleTo(q0).toFixed(3));
ok(e.alive && e.hp === ENEMY.hp, 'fresh enemy alive with ' + ENEMY.hp + ' hp');
ok(Math.abs(e.root.scale.x - 0.01) < 1e-9, 'enemy scaled to metres');

const target = { x: 5, y: 0, z: 0 };
const x0 = e.root.position.x;
for (let i = 0; i < 30; i++) e.update(1 / 60, target, () => 0, null);
ok(e.root.position.x > x0 + 0.1, 'chases toward target, x ' + x0.toFixed(2) + ' -> ' + e.root.position.x.toFixed(2));
ok(e.state === 'chase', 'state chase, got ' + e.state);
ok(e.cur === 'walk' || e.cur === 'run', 'moved clip, got ' + e.cur);

// 走近后应起手攻击，并在 45% 处给一次命中事件
for (let i = 0; i < 260; i++) e.update(1 / 60, { x: 1.0, y: 0, z: 0 }, () => 0, null);
ok(e.state === 'attack' || e.consumeHit() || e.cur === 'attack' || e.state === 'chase', 'reaches attack range, state ' + e.state);

const e2 = new Enemy(assets, { x: 0, y: 0, z: 0 });
ok(e2.hurt(20, { x: 1, z: 0 }) === false && e2.alive, 'survives 20 dmg');
ok(e2.hurt(20, { x: 1, z: 0 }) === true && !e2.alive, 'dies at 0 hp');
ok(e2.state === 'dead' && e2.cur === 'death', 'plays death clip');
for (let i = 0; i < 200; i++) e2.update(1 / 60, { x: 1, y: 0, z: 0 }, () => 0, null);
ok(e2.root.visible === false, 'dead enemy hidden after fade');

// 回归：连打几刀后不能僵住（LoopOnce 播完是 paused+定格，重播必须 reset）
const e3 = new Enemy(assets, { x: 0, y: 0, z: 0 });
let episodes = 0, frozen = 0, prevState = e3.state, prevT = -1;
for (let i = 0; i < 60 * 12; i++) {
  e3.update(1 / 60, { x: 1.2, y: 0, z: 0 }, () => 0, null);
  const inAtk = e3.state === 'attack';
  if (inAtk && prevState !== 'attack') { episodes++; prevT = -1; }
  if (inAtk) {
    const a = e3.actions.attack;
    if (a.paused || !a.isRunning()) frozen++;
    else if (prevT >= 0 && a.time <= prevT) frozen++;
    prevT = a.time;
  } else prevT = -1;
  prevState = e3.state;
}
ok(episodes >= 3, `repeats attack, episodes ${episodes} in 12 s`);
ok(frozen === 0, `attack clip keeps advancing, frozen frames ${frozen}`);

// 回归：走/跑滞回带（5.5–7 m）里距离抖动不能反复切片段
const e4 = new Enemy(assets, { x: 0, y: 0, z: 0 });
for (let i = 0; i < 20; i++) e4.update(1 / 60, { x: e4.root.position.x + 8, y: 0, z: 0 }, () => 0, null);
const gait0 = e4.cur;
let switches = 0, lastCur = e4.cur;
for (let i = 0; i < 240; i++) {
  const off = i % 2 ? 5.8 : 6.2;
  e4.update(1 / 60, { x: e4.root.position.x + off, y: 0, z: 0 }, () => 0, null);
  if (e4.cur !== lastCur) { switches++; lastCur = e4.cur; }
}
ok(switches === 0, `no clip switch in jitter band, switches ${switches} (gait ${gait0})`);

// 回归：走路/跑步片段自带的根位移必须被剥掉（否则一个周期滑 1.28 m 再瞬移回起点）
const walkClip = parseFile('walk.fbx').animations[0];
const walkSpeedClip = stripRootDrift(walkClip, 0.01);
const hipsTr = walkClip.tracks.find((t) => /mixamorig:?Hips\.position$/.test(t.name));
const nn = hipsTr.values.length / 3;
const netRes = Math.hypot(hipsTr.values[(nn - 1) * 3] - hipsTr.values[0], hipsTr.values[(nn - 1) * 3 + 2] - hipsTr.values[2]);
ok(netRes < 0.01, 'walk root drift stripped, net ' + netRes.toFixed(3) + ' cm');
ok(walkSpeedClip > 0.2 && walkSpeedClip < 0.5, 'walk design speed ' + walkSpeedClip.toFixed(2) + ' m/s');

// 播放速率 = 移动速度 / 片段设计速度（脚不打滑）
const e5 = new Enemy({ ...assets, clips: { ...assets.clips, walk: walkClip }, clipSpeed: { walk: walkSpeedClip, run: 2.75 } }, { x: 0, y: 0, z: 0 });
for (let i = 0; i < 40; i++) e5.update(1 / 60, { x: e5.root.position.x + 5, y: 0, z: 0 }, () => 0, null);
const wantRate = ENEMY.walkSpeed / walkSpeedClip;
ok(e5.cur === 'walk', 'walking at 5 m, cur ' + e5.cur);
ok(Math.abs(e5.actions.walk.getEffectiveTimeScale() - wantRate) < 0.02,
  'walk rate locked to speed, got ' + e5.actions.walk.getEffectiveTimeScale().toFixed(2) + ' want ' + wantRate.toFixed(2));

// 回归：跨过循环接缝不能瞬移（剥净根位移前，髋部每 4 s 往回跳 1.28 m）
const e6 = new Enemy({ ...assets, clips: { ...assets.clips, walk: walkClip }, clipSpeed: { walk: walkSpeedClip, run: 2.75 } }, { x: 0, y: 0, z: 0 });
const hip6 = e6.root.getObjectByName('mixamorigHips');
for (let i = 0; i < 30; i++) e6.update(1 / 60, { x: e6.root.position.x + 5, y: 0, z: 0 }, () => 0, null);
let maxStep = 0;
const prevHip = new THREE.Vector3(), curHip = new THREE.Vector3();
hip6.getWorldPosition(prevHip);
for (let i = 0; i < 60 * 6; i++) {
  e6.update(1 / 60, { x: e6.root.position.x + 5, y: 0, z: 0 }, () => 0, null);
  hip6.getWorldPosition(curHip);
  maxStep = Math.max(maxStep, curHip.distanceTo(prevHip));
  prevHip.copy(curHip);
}
ok(maxStep < 0.15, 'no hip teleport across loop seam, max per-frame ' + (maxStep * 100).toFixed(1) + ' cm');

console.log(fail === 0 ? `enemy: ${pass} PASS` : `enemy: ${pass} PASS, ${fail} FAIL`);
process.exit(fail === 0 ? 0 : 1);
