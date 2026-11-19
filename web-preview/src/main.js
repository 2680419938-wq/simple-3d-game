
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { createWorld, stepVertical } from './world.js';
import { setupForestLook, loadForest } from './forest.js';

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e1116);
scene.fog = new THREE.Fog(0x0e1116, 22, 60);

const params = new URLSearchParams(location.search);
const useForest = params.get('scene') !== 'arena';   // 默认森林场景，?scene=arena 回木箱场地
const camera = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.1, 520);

const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
if ('environmentIntensity' in scene) scene.environmentIntensity = 0.55;

const hemi = new THREE.HemisphereLight(0x9fb6d8, 0x1a1f27, 0.55);
scene.add(hemi);

const key = new THREE.DirectionalLight(0xfff3e0, 3.2);
key.position.set(5.5, 9, 4.5);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -7;
key.shadow.camera.right = 7;
key.shadow.camera.top = 7;
key.shadow.camera.bottom = -7;
key.shadow.camera.near = 0.5;
key.shadow.camera.far = 30;
key.shadow.bias = -0.0004;
key.shadow.normalBias = 0.025;
scene.add(key);

const rim = new THREE.DirectionalLight(0x7ea6ff, 1.1);
rim.position.set(-6, 4, -5);
scene.add(rim);

const ground = new THREE.Mesh(
  new THREE.CircleGeometry(60, 72).rotateX(-Math.PI / 2),
  new THREE.MeshStandardMaterial({ color: 0x262b34, roughness: 0.95, metalness: 0 })
);
ground.receiveShadow = true;
scene.add(ground);

const world = createWorld(scene, { arena: !useForest, orbs: !useForest });

const grid = new THREE.GridHelper(60, 60, 0x3d4657, 0x22262e);
grid.material.transparent = true;
grid.material.opacity = 0.5;
grid.position.y = 0.002;
scene.add(grid);

if (useForest) {
  for (const o of [hemi, key, rim, ground, grid]) scene.remove(o);
}

// ---- third person camera rig ----
const rig = {
  yaw: 0.62, // 3/4 front view so the face and the tail both read
  pitch: 0.2,
  dist: 4.0, // __camParams
  target: new THREE.Vector3(0, 1.1, 0),
};

const keys = new Set();
addEventListener('keydown', (e) => {
  keys.add(e.code);
  if (e.code === 'Space') { e.preventDefault(); startJump(); }
});
addEventListener('keyup', (e) => keys.delete(e.code));

let dragging = false;
canvas.addEventListener('pointerdown', (e) => { dragging = true; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener('pointerup', (e) => { dragging = false; canvas.releasePointerCapture(e.pointerId); });
canvas.addEventListener('pointermove', (e) => {
  if (!dragging) return;
  rig.yaw -= e.movementX * 0.005;
  rig.pitch = THREE.MathUtils.clamp(rig.pitch + e.movementY * 0.003, 0.02, 1.15);
});
addEventListener('wheel', (e) => {
  rig.dist = THREE.MathUtils.clamp(rig.dist + e.deltaY * 0.004, 2.5, 14);
}, { passive: true });

if (location.protocol === 'file:') {
  document.getElementById('loading').innerHTML =
    '<b>需要用 HTTP 打开，不能双击 index.html</b><br><br>' +
    '在 <code>web-preview</code> 目录执行 <code>pnpm dev</code>，然后访问 ' +
    '<a style="color:#7ea6ff" href="http://localhost:5199/">http://localhost:5199/</a>';
}

const demo = params.get('demo');
const lodParam = params.get('lod');
if (demo === 'walk' || demo === 'run') keys.add('KeyW');
if (demo === 'run') keys.add('ShiftLeft');
if (demo === 'strafe') keys.add('KeyD');

const stateEl = document.getElementById('state');
if (params.has('yaw')) rig.yaw = parseFloat(params.get('yaw')); // __camParams
if (params.has('pitch')) rig.pitch = parseFloat(params.get('pitch'));
if (params.has('dist')) rig.dist = parseFloat(params.get('dist'));
const statsEl = document.getElementById('stats');

let mixer = null;
let model = null;
const clips = { idle: null, walk: null, run: null, jump: null, crouch: null, crouchwalk: null };
const actions = { idle: null, walk: null, run: null, jump: null, crouch: null, crouchwalk: null };
const CROUCH_SPEED = 1.3;   // 蹲走支撑脚实测 0.44m/16帧 与 0.34m/13帧 → 0.6~1.0 m/s，取 0.9
const CROUCH_RATE = 1.5;   // Crouching.fbx 99 帧 @24fps，1.5× 下蹲约 2.7 s
const JUMP_RATE = 1.35;   // 跳跃原长 1.875 s，加快到 ~1.39 s
let jumpT = 0;            // 剩余跳跃时间，>0 时压住行走状态机
const WALK_SPEED = 0.66;   // 异形 walk：36.4 帧/循环 @24fps，单脚支撑位移 0.50 m → 0.66 m/s
const RUN_SPEED = 5.30;    // 真 Run 动作（Fast Run 重定向）：支撑脚实测后退 0.22 m/帧 @24fps → 5.3 m/s
const LEAN_MAX = 0.15;     // 跑时前倾 8.6°，让加速的 Walk 读起来像冲刺
let curAnim = 'idle';
let modelYaw = 0;         // 目标朝向（弧度），前倾在它之上叠加
let lean = 0;             // 当前前倾角（弧度）
const X_AXIS = new THREE.Vector3(1, 0, 0);
const tmpQ2 = new THREE.Quaternion();
const clock = new THREE.Clock();

function setAnim(name, fade = 0.25) {
  if (name === curAnim || !actions[name]) return;
  const from = actions[curAnim], to = actions[name];
  const fromCrouchWalk = curAnim === 'crouchwalk';
  to.reset();   // reset() 会清掉 paused（LoopOnce+clampWhenFinished 播完会置 paused，不清就永远停在最后一帧）
  to.setEffectiveTimeScale(1); to.setEffectiveWeight(1);
  // 从蹲走回到蹲待机时，直接跳到 Crouch 的末帧（蹲姿），否则会把「从站姿蹲下」整段重播一遍，看起来像站起来
  if (name === 'crouch' && fromCrouchWalk) to.time = Math.max(0, to.getClip().duration - 0.05);
  to.play();
  if (from) from.crossFadeTo(to, fade, false);
  curAnim = name;
}

const dbgEl = document.getElementById('dbg');
const dbg = (s) => { if (dbgEl && params.has('dbg')) dbgEl.textContent += s + '\n'; };
let forestLook = null;
if (useForest) {
  forestLook = setupForestLook(scene, renderer);
  loadForest(scene, '/Forest_Morning.glb', (res) => {
    world.addBoxes(res.boxes);
    const pts = [];
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2 + 0.35;
      pts.push([Math.cos(a) * (5.5 + (i % 3) * 3.0), 0.55, Math.sin(a) * (5.5 + (i % 3) * 3.0)]);
    }
    world.addOrbs(pts);
    window.__forest = { trunks: res.boxes.length, orbs: world.total };
    const bb = new THREE.Box3().setFromObject(res.root);
    dbg('forest ok: trunks ' + res.boxes.length + ' orbs ' + world.total);
    dbg('bbox ' + bb.min.toArray().map((v) => v.toFixed(1)).join(',') + ' -> ' + bb.max.toArray().map((v) => v.toFixed(1)).join(','));
    const widths = res.boxes.map((b) => Math.max(b.maxx - b.minx, b.maxz - b.minz)).sort((a, b) => b - a);
    dbg('trunk w max ' + widths[0].toFixed(2) + ' med ' + widths[Math.floor(widths.length / 2)].toFixed(2));
    dbg('boxes ' + res.boxes.slice(0, 3).map((b) => '[' + ((b.minx + b.maxx) / 2).toFixed(1) + ',' + ((b.minz + b.maxz) / 2).toFixed(1) + ' w' + Math.max(b.maxx - b.minx, b.maxz - b.minz).toFixed(1) + ']').join(' '));
    console.log('forest ready: trunks', res.boxes.length, 'orbs', world.total);
  }, (e) => { dbg('forest ERR ' + (e && e.message)); console.error('forest load failed', e); });
}

const glbParam = params.get('glb'); // ?glb=/DragonMan_Std_TPose.glb
const glbUrl = glbParam
  ? (glbParam.startsWith('/') ? glbParam : '/' + glbParam)
  : lodParam === '1' ? '/DragonMan_Game_LOD1.glb'
  : lodParam === '2' ? '/DragonMan_Game_LOD2.glb'
  : '/Alien_Walk_Jump_2k.glb';
const freezeT = params.has('freeze') ? parseFloat(params.get('freeze')) : null; // __freezeT
new GLTFLoader().load(glbUrl, (gltf) => {
  model = gltf.scene;
  model.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
      o.frustumCulled = false;
    }
  });
  scene.add(model);

  key.target = model;
  scene.add(key.target);

  mixer = new THREE.AnimationMixer(model);
  // 34-bone package ships Idle_Lively + Walk; pick each by name, fall back to first clip
  const byName = (n) => gltf.animations.find((a) => a.name === n);
  clips.idle = byName('Idle') || byName('Idle_Lively') || gltf.animations[0] || null;
  clips.walk = byName('Walk') || null;
  clips.run = byName('Run') || null;
  clips.jump = byName('Jump') || null;
  clips.crouch = byName('Crouch') || null;
  const cwRaw = byName('CrouchB') || byName('CrouchWalk');
  // 原片 1..43 帧几乎不动（两脚位移 < 3 cm），真正的迈步在 49..73 帧；只取这一段当循环
  clips.crouchwalk = cwRaw || null;   // Crouched Walking：26 帧 1.04 s，首末帧完全一致（seam 0.001）可直循环
  clips.crouch = cwRaw ? THREE.AnimationUtils.subclip(cwRaw, 'CrouchIdle', 1, 2, 24) : clips.crouch;   // 蹲待机 = 同一动作的第 1 帧姿态（双脚并拢）
  if (clips.idle) { actions.idle = mixer.clipAction(clips.idle); actions.idle.play(); }
  for (const k of ['walk', 'run', 'jump', 'crouch', 'crouchwalk']) {
    if (!clips[k]) continue;
    actions[k] = mixer.clipAction(clips[k]);
    actions[k].play();
    actions[k].enabled = false;
    actions[k].setEffectiveWeight(0);
  }
  if (actions.crouch) {
    actions.crouch.setLoop(THREE.LoopOnce, 1);
    actions.crouch.clampWhenFinished = true;     // 蹲到底保持姿势，起身靠交叉淡出
  }
  const hasRun = !!actions.run;
  // ?freeze=<t> 定格某一帧；?clip=run|walk|idle 指定定格哪个动作
  if (freezeT !== null) {
    const want = params.get('clip');
    const k = (want && actions[want]) ? want
      : actions.walk ? 'walk' : actions.idle ? 'idle' : actions.run ? 'run' : null;
    if (!k) { console.warn('no clip to freeze'); }
    for (const n of ['idle', 'walk', 'run', 'jump']) {
      if (!actions[n]) continue;
      actions[n].stop();
      actions[n].enabled = false;
      actions[n].setEffectiveWeight(0);
    }
    const a = actions[k];
    if (a) {
    a.reset();
    a.play();
    a.paused = true;
    a.enabled = true;
    a.setEffectiveWeight(1);
    a.time = Math.min(freezeT, a.getClip().duration - 0.001);
    mixer.update(0);
    window.__frozen = k;
    }
  }

  document.getElementById('loading').remove();
  const lodName = useForest
    ? 'Forest_Morning + ' + glbUrl.split('/').pop()
    : { '0': 'LOD0', '1': 'LOD1', '2': 'LOD2' }[lodParam] || glbUrl.split('/').pop();
  const clip0 = clips.idle;
  document.getElementById('lodname').textContent = lodName;
  document.getElementById('cliplist').textContent =
    gltf.animations.map((a) => a.name + ' ' + a.duration.toFixed(2) + 's').join(' + ') +
    (hasRun ? '' : ' · Shift = 跑（Run 5.3 m/s）');
  window.__clips = { hasRun, names: gltf.animations.map((a) => a.name) };
  if (params.has('pos')) {                      // __spawnAt  例：?pos=-4.4,3.0
    const [sx, sz] = params.get('pos').split(',').map(Number);
    model.position.set(sx, 0, sz);
    py = world.groundAt(sx, sz, 3.0);
    model.position.y = py;
  }
  if (params.has('crouch')) setTimeout(() => { crouched = true; }, Number(params.get('cd')) || 300);   // __crouchAuto
  if (params.has('jump')) setTimeout(startJump, Number(params.get('jd')) || 250);   // __jumpAuto
  window.__ready = true;
  console.log('clips:', gltf.animations.map((a) => a.name + ' ' + a.duration.toFixed(2) + 's').join(', '));
}, undefined, (err) => {
  const el = document.getElementById('loading');
  if (location.protocol === 'file:') {
    el.innerHTML = '<b>需要用 HTTP 打开，不能双击 index.html</b><br><br>' +
      '在 <code>web-preview</code> 目录执行 <code>pnpm dev</code>，然后访问 ' +
      '<a style="color:#7ea6ff" href="http://localhost:5199/">http://localhost:5199/</a><br>' +
      '（file:// 打开时浏览器会拦截 ES 模块和 .glb 的读取）';
  } else {
    el.textContent = 'load failed: ' + err.message + '（检查 public/ 下是否有 ' + glbUrl + '）';
  }
  console.error(err);
});

function startJump() {
  const a = actions.jump;
  if (!a || jumpT > 0 || !grounded || takeoffT >= 0 || crouched) return;
  takeoffT = 0.38;   // 蓄力段结束才起跳，和 Jump 动作的离地帧对齐
  const from = actions[curAnim];
  a.reset();
  a.setLoop(THREE.LoopOnce, 1);
  a.clampWhenFinished = true;
  a.enabled = true;
  a.setEffectiveTimeScale(JUMP_RATE);
  a.setEffectiveWeight(1);
  a.play();
  if (from && from !== a) from.crossFadeTo(a, 0.10, false);
  curAnim = 'jump';
  jumpT = a.getClip().duration / JUMP_RATE;
}

const forward = new THREE.Vector3();
const right = new THREE.Vector3();
const moveDir = new THREE.Vector3();
const camPos = new THREE.Vector3();
const desiredCam = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);
const tmpQ = new THREE.Quaternion();
let camInit = false;
let speed = 0;

// ---- 玩法状态：重力、跳跃冲量、收集进度 ----
const PLAYER_R = 0.55;
const GRAV = 16.3;
const JUMP_V = 5.4;      // 顶点 0.89 m、滞空 0.66 s：够跳上 0.5 m 一级的箱子，也和 Jump 动作的落地帧对得上
let py = 0, vy = 0, grounded = true, takeoffT = -1;
let collected = 0, playTime = 0, finished = false;
let crouched = false;   // C 键切换：蹲下（这个动作只有下蹲过程，起身用 0.35 s 淡出回站立）
const gameEl = document.getElementById('game');
function resetGame() {
  py = 0; vy = 0; grounded = true; takeoffT = -1;
  collected = 0; playTime = 0; finished = false;
  if (model) { model.position.set(0, 0, 0); modelYaw = 0; }
  for (const o of world.orbs) { o.taken = false; o.mesh.visible = true; o.ring.visible = true; }
}
addEventListener('keydown', (e) => {
  if (e.code === 'KeyR') resetGame();
  if (e.code === 'KeyC' && (actions.crouch || actions.crouchwalk) && grounded) crouched = !crouched;
});

function update(dt) {
  // movement is camera relative; W pushes away from the camera
  forward.set(-Math.sin(rig.yaw), 0, -Math.cos(rig.yaw)).normalize();
  right.crossVectors(forward, UP).normalize();   // forward x up = 屏幕右方（UP x forward 得到左方，A/D 会反）

  let ix = 0, iz = 0;
  if (keys.has('KeyW') || keys.has('ArrowUp')) iz += 1;
  if (keys.has('KeyS') || keys.has('ArrowDown')) iz -= 1;
  if (keys.has('KeyD') || keys.has('ArrowRight')) ix += 1;
  if (keys.has('KeyA') || keys.has('ArrowLeft')) ix -= 1;

  moveDir.set(0, 0, 0).addScaledVector(forward, iz).addScaledVector(right, ix);
  const moving = moveDir.lengthSq() > 0 && !!model;   // 蹲下时锁住移动（缺 Crouch Walk）
  const running = keys.has('ShiftLeft') || keys.has('ShiftRight');
  const targetSpeed = !moving ? 0 : crouched ? CROUCH_SPEED : running ? RUN_SPEED : WALK_SPEED;
  speed += (targetSpeed - speed) * Math.min(1, dt * 9);
  // pick the clip for the current state; playback rate tracks real speed so feet stop sliding
  let want = crouched
    ? (moving && actions.crouchwalk ? 'crouchwalk' : 'crouch')
    : (!moving ? 'idle' : running ? 'run' : 'walk');
  if (!actions[want]) want = moving ? 'walk' : 'idle';
  if (!actions[want]) want = 'idle';
  if (jumpT > 0) {
    jumpT = Math.max(0, jumpT - dt);
    if (jumpT === 0) { curAnim = 'jump'; setAnim(want); }
  } else setAnim(want, crouched && (want === 'crouch' || want === 'crouchwalk') ? 0.12 : 0.25);
  if (actions.walk) actions.walk.setEffectiveTimeScale(THREE.MathUtils.clamp(speed / WALK_SPEED, 0.45, 2.0));
  if (actions.run) actions.run.setEffectiveTimeScale(THREE.MathUtils.clamp(speed / RUN_SPEED, 0.4, 1.25));
  if (actions.crouchwalk) actions.crouchwalk.setEffectiveTimeScale(THREE.MathUtils.clamp(speed / CROUCH_SPEED, 0.6, 1.6));

  if (model) {
    if (moving) {
      moveDir.normalize();
      modelYaw = Math.atan2(moveDir.x, moveDir.z); // model faces +Z
    }
    // run reads as a sprint: lean the whole body into the direction of travel
    const leanTarget = THREE.MathUtils.clamp((speed - WALK_SPEED) / (RUN_SPEED - WALK_SPEED), 0, 1) * LEAN_MAX;
    lean += (leanTarget - lean) * Math.min(1, dt * 6);
    tmpQ.setFromAxisAngle(UP, modelYaw);
    tmpQ2.setFromAxisAngle(X_AXIS, lean);
    tmpQ.multiply(tmpQ2);
    model.quaternion.slerp(tmpQ, Math.min(1, dt * 10));
    model.position.addScaledVector(moveDir, speed * dt);
    world.resolve(model.position, PLAYER_R, py);

    // 起跳冲量在蓄力结束时施加
    if (takeoffT >= 0) {
      takeoffT -= dt;
      if (takeoffT < 0) { vy = JUMP_V; }
    }
    const gh = world.groundAt(model.position.x, model.position.z, py);
    const st = stepVertical({ py, vy, grounded }, dt, GRAV, gh);
    py = st.py; vy = st.vy; grounded = st.grounded;
    model.position.y = py;

    if (!finished) {
      collected += world.tick(dt, performance.now() / 1000, { x: model.position.x, y: py, z: model.position.z });
      playTime += dt;
      if (world.total > 0 && collected >= world.total) { finished = true; jumpT = 0; }
    } else {
      world.tick(dt, performance.now() / 1000, { x: 1e9, y: 0, z: 0 });
    }
    if (gameEl) {
      gameEl.textContent = finished
        ? `通关！${playTime.toFixed(1)} s · 按 R 重开`
        : `收集 ${collected} / ${world.total} · ${playTime.toFixed(1)} s`;
      gameEl.classList.toggle('win', finished);
    }
    rig.target.lerp(
      new THREE.Vector3(model.position.x, model.position.y + (crouched ? 1.05 : 1.45), model.position.z),
      Math.min(1, dt * 7)
    );
  }

  const dist = rig.dist + Math.min(speed, 5) * 0.32;  // pull back while running
  const h = Math.cos(rig.pitch) * dist;
  desiredCam.set(
    rig.target.x + Math.sin(rig.yaw) * h,
    rig.target.y + Math.sin(rig.pitch) * dist,
    rig.target.z + Math.cos(rig.yaw) * h
  );
  if (!camInit) { camera.position.copy(desiredCam); camInit = true; }
  else camera.position.lerp(desiredCam, Math.min(1, dt * 6));
  camera.lookAt(rig.target);

  if (forestLook && model) {
    forestLook.sun.position.copy(model.position).addScaledVector(forestLook.sunDir, 60);
    forestLook.sun.target.position.copy(model.position);
    forestLook.sun.target.updateMatrixWorld();
    forestLook.sun.shadow.camera.updateProjectionMatrix();
    forestLook.sky.position.copy(camera.position);
  }
  key.position.set(model ? model.position.x + 5.5 : 5.5, 9, model ? model.position.z + 4.5 : 4.5);
  ground.position.set(model ? model.position.x : 0, 0, model ? model.position.z : 0);
  grid.position.x = ground.position.x;
  grid.position.z = ground.position.z;

  if (params.has('dbg') && dbgEl) {
    const f = (n) => {
      const a = actions[n];
      return a ? n + ':t' + a.time.toFixed(2) + '/w' + a.getEffectiveWeight().toFixed(2) + (a.paused ? '/P' : '') : n + ':--';
    };
    dbgEl.textContent = [f('crouch'), f('crouchwalk'), f('walk'), 'cur=' + curAnim, 'crouched=' + crouched].join('  ');
  }
  if (mixer && !window.__frozen) mixer.update(dt);

  if (model && stateEl) {
    stateEl.textContent =
      `pos ${model.position.x.toFixed(1)}, ${model.position.z.toFixed(1)} · y ${py.toFixed(2)} · speed ${speed.toFixed(1)} m/s · clip ${(jumpT > 0 ? 'jump' : want).toUpperCase()}${grounded ? '' : ' · 空中'}`;
  }
}

let acc = 0, frames = 0;
function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  update(dt);
  renderer.render(scene, camera);
  frames++; acc += dt;
  if (acc > 0.5) {
    const tri = renderer.info.render.triangles;
    statsEl.textContent = `${(frames / acc).toFixed(0)} fps · ${tri.toLocaleString()} tri · ${renderer.info.render.calls} draw`;
    frames = 0; acc = 0;
  }
  requestAnimationFrame(tick);
}
tick();

addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});