// 敌人模块的结构/状态机测试（不依赖浏览器）：node test/enemy.mjs
import { readFileSync } from 'node:fs';
import * as THREE from 'three';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { buildPuppet, Enemy, ENEMY } from '../src/enemy.js';

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

console.log(fail === 0 ? `enemy: ${pass} PASS` : `enemy: ${pass} PASS, ${fail} FAIL`);
process.exit(fail === 0 ? 0 : 1);
