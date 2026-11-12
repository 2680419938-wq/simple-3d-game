
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

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

const camera = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.1, 200);

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

const grid = new THREE.GridHelper(60, 60, 0x3d4657, 0x22262e);
grid.material.transparent = true;
grid.material.opacity = 0.5;
grid.position.y = 0.002;
scene.add(grid);

// ---- third person camera rig ----
const rig = {
  yaw: 0.62, // 3/4 front view so the face and the tail both read
  pitch: 0.2,
  dist: 6.2, // __camParams
  target: new THREE.Vector3(0, 1.1, 0),
};

const keys = new Set();
addEventListener('keydown', (e) => keys.add(e.code));
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

const params = new URLSearchParams(location.search);
const demo = params.get('demo');
const lodParam = params.get('lod');
if (demo === 'walk' || demo === 'run') keys.add('KeyW');
if (demo === 'run') keys.add('ShiftLeft');

const stateEl = document.getElementById('state');
if (params.has('yaw')) rig.yaw = parseFloat(params.get('yaw')); // __camParams
if (params.has('pitch')) rig.pitch = parseFloat(params.get('pitch'));
if (params.has('dist')) rig.dist = parseFloat(params.get('dist'));
const statsEl = document.getElementById('stats');

let mixer = null;
let model = null;
const clips = { idle: null, walk: null, run: null };
const actions = { idle: null, walk: null, run: null };
const WALK_SPEED = 0.61;   // authored walk: 0.324 m per side / 1.0667 s
const RUN_SPEED = 2.83;    // authored run: 0.85 m stride, 0.6 s cycle
let curAnim = 'idle';
const clock = new THREE.Clock();

function setAnim(name) {
  if (name === curAnim || !actions[name]) return;
  const from = actions[curAnim], to = actions[name];
  to.enabled = true; to.setEffectiveTimeScale(1); to.setEffectiveWeight(1);
  to.time = 0; to.play();
  if (from) from.crossFadeTo(to, 0.25, false);
  curAnim = name;
}

const glbParam = params.get('glb'); // ?glb=/DragonMan_Std_TPose.glb
const glbUrl = glbParam
  ? (glbParam.startsWith('/') ? glbParam : '/' + glbParam)
  : lodParam === '1' ? '/DragonMan_Game_LOD1.glb'
  : lodParam === '2' ? '/DragonMan_Game_LOD2.glb'
  : '/DragonMan_New.glb';
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
  clips.idle = byName('Idle_Lively') || gltf.animations[0] || null;
  clips.walk = byName('Walk') || null;
  clips.run = byName('Run') || null;
  if (clips.idle) { actions.idle = mixer.clipAction(clips.idle); actions.idle.play(); }
  for (const k of ['walk', 'run']) {
    if (!clips[k]) continue;
    actions[k] = mixer.clipAction(clips[k]);
    actions[k].play();
    actions[k].enabled = false;
    actions[k].setEffectiveWeight(0);
  }
  const hasRun = !!actions.run;
  if (freezeT !== null && clips.walk) {
    actions.idle.stop();
    actions.walk.enabled = true;
    actions.walk.setEffectiveWeight(1);
    actions.walk.paused = true;
    actions.walk.time = freezeT;
    mixer.update(0);
    window.__frozen = true;
  }

  document.getElementById('loading').remove();
  const lodName = { '0': 'LOD0', '1': 'LOD1', '2': 'LOD2' }[lodParam] || (glbParam ? glbParam.split('/').pop() : '标准包 70 骨');
  const clip0 = clips.idle;
  document.getElementById('lodname').textContent =
    lodName + ' · ' + gltf.animations.map((a) => a.name + ' ' + a.duration.toFixed(2) + 's').join(' + ') +
    (hasRun ? '' : ' · 无 Run 动作（Shift 时加快走路）');
  window.__clips = { hasRun, names: gltf.animations.map((a) => a.name) };
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

const forward = new THREE.Vector3();
const right = new THREE.Vector3();
const moveDir = new THREE.Vector3();
const camPos = new THREE.Vector3();
const desiredCam = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);
const tmpQ = new THREE.Quaternion();
let camInit = false;
let speed = 0;

function update(dt) {
  // movement is camera relative; W pushes away from the camera
  forward.set(-Math.sin(rig.yaw), 0, -Math.cos(rig.yaw)).normalize();
  right.crossVectors(UP, forward).normalize();

  let ix = 0, iz = 0;
  if (keys.has('KeyW') || keys.has('ArrowUp')) iz += 1;
  if (keys.has('KeyS') || keys.has('ArrowDown')) iz -= 1;
  if (keys.has('KeyD') || keys.has('ArrowRight')) ix += 1;
  if (keys.has('KeyA') || keys.has('ArrowLeft')) ix -= 1;

  moveDir.set(0, 0, 0).addScaledVector(forward, iz).addScaledVector(right, ix);
  const moving = moveDir.lengthSq() > 0 && !!model;
  const running = keys.has('ShiftLeft') || keys.has('ShiftRight');
  const targetSpeed = moving ? (running ? RUN_SPEED : WALK_SPEED) : 0;
  speed += (targetSpeed - speed) * Math.min(1, dt * 9);
  // pick the clip for the current state; playback rate tracks real speed so feet stop sliding
  let want = !moving ? 'idle' : running ? 'run' : 'walk';
  if (!actions[want]) want = moving ? 'walk' : 'idle';
  if (!actions[want]) want = 'idle';
  setAnim(want);
  if (actions.walk) actions.walk.setEffectiveTimeScale(THREE.MathUtils.clamp(speed / WALK_SPEED, 0.45, 1.8));
  if (actions.run) actions.run.setEffectiveTimeScale(THREE.MathUtils.clamp(speed / RUN_SPEED, 0.5, 1.6));

  if (model) {
    if (moving) {
      moveDir.normalize();
      const yaw = Math.atan2(moveDir.x, moveDir.z); // model faces +Z
      tmpQ.setFromAxisAngle(UP, yaw);
      model.quaternion.slerp(tmpQ, Math.min(1, dt * 10));
    }
    model.position.addScaledVector(moveDir, speed * dt);
    model.position.y = 0;
    rig.target.lerp(
      new THREE.Vector3(model.position.x, model.position.y + 1.45, model.position.z),
      Math.min(1, dt * 7)
    );
  }

  const dist = rig.dist + Math.min(speed, 3) * 0.5;  // pull back while running
  const h = Math.cos(rig.pitch) * dist;
  desiredCam.set(
    rig.target.x + Math.sin(rig.yaw) * h,
    rig.target.y + Math.sin(rig.pitch) * dist,
    rig.target.z + Math.cos(rig.yaw) * h
  );
  if (!camInit) { camera.position.copy(desiredCam); camInit = true; }
  else camera.position.lerp(desiredCam, Math.min(1, dt * 6));
  camera.lookAt(rig.target);

  key.position.set(model ? model.position.x + 5.5 : 5.5, 9, model ? model.position.z + 4.5 : 4.5);
  ground.position.set(model ? model.position.x : 0, 0, model ? model.position.z : 0);
  grid.position.x = ground.position.x;
  grid.position.z = ground.position.z;

  if (mixer && !window.__frozen) mixer.update(dt);

  if (model && stateEl) {
    stateEl.textContent =
      `pos ${model.position.x.toFixed(1)}, ${model.position.z.toFixed(1)} · speed ${speed.toFixed(1)} m/s · clip ${want.toUpperCase()}`;
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