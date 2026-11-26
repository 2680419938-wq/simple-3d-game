// 烘好的敌人 GLB（AnimLib/zombiegirl_build.py 产物）：骨架/动作/贴图/尺寸自检
// node 里 GLTFLoader 没有 DOM 与 ImageBitmap，先把纹理解析掉再喂给它
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { stripRootDrift, ENEMY } from '../src/enemy.js';

const GLB = new URL('../public/models/zombie/zombiegirl.glb', import.meta.url);

function stripTextures(buf) {
  const jsonLen = buf.readUInt32LE(12);
  const json = JSON.parse(buf.subarray(20, 20 + jsonLen).toString('utf8'));
  const binStart = 20 + jsonLen;
  const binLen = buf.readUInt32LE(binStart), binType = buf.readUInt32LE(binStart + 4);
  const bin = buf.subarray(binStart + 8, binStart + 8 + binLen);
  const anims = (json.animations || []).map((a) => a.name);
  delete json.images; delete json.textures; delete json.samplers;
  delete json.extensionsUsed; delete json.extensionsRequired;
  for (const m of json.materials || []) {
    delete m.extensions;
    for (const k of Object.keys(m)) {
      if (k.endsWith('Texture')) delete m[k];
      if (k === 'pbrMetallicRoughness') for (const kk of Object.keys(m[k])) if (kk.endsWith('Texture')) delete m[k][kk];
    }
  }
  let js = Buffer.from(JSON.stringify(json), 'utf8');
  while (js.length % 4) js = Buffer.concat([js, Buffer.from(' ')]);
  const out = Buffer.alloc(12 + 8 + js.length + 8 + bin.length);
  out.write('glTF', 0, 'ascii'); out.writeUInt32LE(2, 4); out.writeUInt32LE(out.length, 8);
  out.writeUInt32LE(js.length, 12); out.writeUInt32LE(0x4e4f534a, 16); js.copy(out, 20);
  const off = 20 + js.length;
  out.writeUInt32LE(bin.length, off); out.writeUInt32LE(binType, off + 4); bin.copy(out, off + 8);
  return { out, animNames: anims };
}

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('FAIL', m); } };

const raw = readFileSync(GLB);
ok(raw.length > 1e6, 'glb has payload, ' + raw.length + ' B');
const { out, animNames } = stripTextures(raw);
const tmp = join(tmpdir(), 'zombiegirl_notex.glb');
writeFileSync(tmp, out);
const ab = readFileSync(tmp).buffer;
const gltf = await new Promise((res, rej) => new GLTFLoader().parse(ab.slice(0), '', res, rej));
unlinkSync(tmp);

const scene = gltf.scene;
ok(Math.abs(scene.scale.x - 1) < 1e-3, 'root scale baked to 1 (0.01 lives on Armature), got ' + scene.scale.x);

const want = ['idle', 'walk', 'run', 'attack', 'death'];
ok(want.every((n) => animNames.includes(n)), 'glb carries 5 clips, got ' + animNames.join(','));
ok(gltf.animations.every((c) => c.tracks.length >= 150), 'clips drive the whole skeleton, min tracks ' + Math.min(...gltf.animations.map((c) => c.tracks.length)));

let skin = 0, tris = 0;
scene.traverse((o) => { if (o.isSkinnedMesh) { skin++; tris += o.geometry.index.count / 3; } });
ok(skin === 7, '3 meshes split into 7 primitives by material, got ' + skin);
ok(Math.abs(tris - 7448) < 100, 'tris ~7448, got ' + Math.round(tris));

const bone = (n) => scene.getObjectByName(n);
const v = new THREE.Vector3();
const wy = (o) => (o ? o.getWorldPosition(v).y : NaN);
scene.updateMatrixWorld(true);
ok(Math.abs(wy(bone('mixamorigHips')) - 1.08) < 0.06, 'rest hips at 1.08 m, got ' + wy(bone('mixamorigHips')).toFixed(3));
ok(Math.abs(wy(bone('mixamorigHead')) - 1.82) < 0.08, 'rest head at 1.82 m, got ' + wy(bone('mixamorigHead')).toFixed(3));

// 逐条播一遍：躯干必须保持竖直（曾经用 FBX 原始 clip 直接套会整个人躺倒）
const mixer = new THREE.AnimationMixer(scene);
for (const c of gltf.animations) {
  mixer.stopAllAction();
  const a = mixer.clipAction(c); a.reset(); a.play();
  for (let i = 0; i < 30; i++) mixer.update(1 / 30);
  const hips = wy(bone('mixamorigHips')), head = wy(bone('mixamorigHead'));
  ok(head > 1.35 && hips > 0.6 && hips < 1.25, c.name + ' stays upright (hips ' + hips.toFixed(2) + ', head ' + head.toFixed(2) + ')');
}
ok(gltf.animations.find((c) => c.name === 'attack').duration > 2.4, 'attack clip long enough to read');

// 根位移剥离：GLB 里漂移落在轨道 y 上（FBX 是 z），三个分量都要算，否则设计地速会算成 0，
// 播放速率 = 移动速度 / 0 → 片段被放到几十万倍速，看起来就是原地抽搐。
const walkC = gltf.animations.find((c) => c.name === 'walk');
const wv = walkC.tracks.find((t) => /mixamorig:?Hips\.position$/.test(t.name)).values;
const wsave = Float32Array.from(wv);
const sp = stripRootDrift(walkC, 0.01);
ok(Math.abs(sp - 0.31) < 0.05, 'walk design speed ~0.31 m/s (drift lives on track y), got ' + sp.toFixed(3));
ok(ENEMY.walkSpeed / sp < 4, 'walk timeScale stays sane, got ' + (ENEMY.walkSpeed / sp).toFixed(2));
wv.set(wsave);

const runC = gltf.animations.find((c) => c.name === 'run');
const rv = runC.tracks.find((t) => /mixamorig:?Hips\.position$/.test(t.name)).values;
const rsave = Float32Array.from(rv);
const spr = stripRootDrift(runC, 0.01);
ok(Math.abs(spr - 2.77) < 0.45, 'run design speed ~2.77 m/s, got ' + spr.toFixed(3));
rv.set(rsave);

// 剥完再整周期播一遍：髋部不能有任何单帧瞬移
stripRootDrift(walkC, 0.01);
const m2 = new THREE.AnimationMixer(scene);
m2.stopAllAction();
const a2 = m2.clipAction(walkC); a2.reset(); a2.play();
const hp = new THREE.Vector3(), prevHp = new THREE.Vector3();
let maxSite = 0;
for (let i = 0; i <= Math.ceil(walkC.duration * 60); i++) {
  m2.update(1 / 60);
  scene.updateMatrixWorld(true);
  bone('mixamorigHips').getWorldPosition(hp);
  if (i) maxSite = Math.max(maxSite, hp.distanceTo(prevHp));
  prevHp.copy(hp);
}
ok(maxSite < 0.05, 'no hip teleport across walk loop after strip, max per-frame ' + (maxSite * 100).toFixed(1) + ' cm');
wv.set(wsave);
console.log(fail === 0 ? 'enemyglb: ' + pass + ' PASS' : 'enemyglb: ' + pass + ' PASS, ' + fail + ' FAIL');
