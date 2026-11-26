
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { createWorld, stepVertical } from './world.js';
import { setupForestLook, loadForest } from './forest.js';
import { addAtmo } from './atmo.js';
import { createPostFX } from './postfx.js';
import { createVfx } from './vfx.js';
import { createSkills } from './skills.js';
import { Progression, SKILL_META, SLOTS, POOL, cardText } from './progression.js';
import { loadEnemyAssets, Enemy, ENEMY } from './enemy.js';

const ATMO_SCALE = 0.25;   // 线性空间加色约比 sRGB 亮 4 倍，0.25 与原观感对齐

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
camera.layers.enable(1);            // layer1 = demo 技能特效（闪电/粒子/贴花都在 VFX 层）
camera.layers.enable(2);            // layer2 = 事件特效，故意排除在光柱用的深度通道外

const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const vfx = createVfx(scene, camera);
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
const JUMP_RATE = 1.15;   // 片段滞空 0.75 s / 物理滞空 0.663 s → 1.13~1.15，起跳与落地帧才对得上   // 跳跃原长 1.875 s，加快到 ~1.39 s
let jumpT = 0;            // 剩余跳跃时间，>0 时压住行走状态机
let skillDemo = params.get('skill');   // ?skill=ice|thunder 自动放一次技能，截图用
let fxDemo = params.get('fx');     // ?fx=land|pickup 循环触发特效；配合 &fxhold=<秒> 定格在该相位
let fxNext = 0;
let fxFrozen = false;
let sprintT = 0;
const picked = [];   // 本帧收集到的球，复用一个数组避免每帧分配
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
let atmo = null;
let sunT = 0;
let postfx = null;
if (useForest) {
  forestLook = setupForestLook(scene, renderer);
  postfx = createPostFX(renderer, scene, camera, {
    strength: params.has('bs') ? parseFloat(params.get('bs')) : 0.60,
    threshold: params.has('bt') ? parseFloat(params.get('bt')) : 0.70,
  });
  postfx.setEnabled(params.get('bloom') !== '0');   // ?bloom=0 关掉辉光做对照
  atmo = addAtmo(scene, forestLook.sunDir, params.get('soft') === '0' ? null : postfx.depth,
    { scale: ATMO_SCALE * (params.has('fogx') ? parseFloat(params.get('fogx')) : 1.0) });
  camera.layers.enable(1);                          // layer1 = 光柱/雾片（深度图里要排除它们）
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
  const jRaw = byName('Jump');
  // 砍掉前 8 帧（0.29 s）的蓄力，起跳更快；剩 8..46 帧 = 1.58 s
  clips.jump = jRaw ? THREE.AnimationUtils.subclip(jRaw, 'Jump', 8, 46, 24) : null;
  clips.crouch = byName('Crouch') || null;
  const cwRaw = byName('CrouchB') || byName('CrouchWalk');
  // 原片 1..43 帧几乎不动（两脚位移 < 3 cm），真正的迈步在 49..73 帧；只取这一段当循环
  clips.crouchwalk = cwRaw || null;   // Crouched Walking：26 帧 1.04 s，首末帧完全一致（seam 0.001）可直循环
  clips.crouch = cwRaw ? THREE.AnimationUtils.subclip(cwRaw, 'CrouchIdle', 1, 2, 24) : clips.crouch;   // 蹲待机 = 同一动作的第 1 帧姿态（双脚并拢）
  // 攻击：源片 34 帧 30fps，导出后 27 帧；取 3..19 帧（甩臂横扫），1.10 倍速 → 0.61 s
  const atkRaw = byName('Attack');
  clips.attack = atkRaw ? THREE.AnimationUtils.subclip(atkRaw, 'Attack', 3, 19, 24) : null;
  if (clips.attack) ATK_TOTAL = clips.attack.duration / ATK_RATE;
  // 受击：源片 53 帧 24fps（原地已剥掉 0.8 m 后退漂移）；取 9..33 帧（挨打 → 弯腰最深 → 抬到一半），1.9 倍速 → 0.53 s
  const hurtRaw = byName('Hurt');
  clips.hurt = hurtRaw ? THREE.AnimationUtils.subclip(hurtRaw, 'Hurt', 9, 33, 24) : null;
  if (clips.hurt) HURT_TOTAL = clips.hurt.duration / HURT_RATE;
  if (clips.idle) { actions.idle = mixer.clipAction(clips.idle); actions.idle.play(); }
  for (const k of ['walk', 'run', 'jump', 'crouch', 'crouchwalk', 'attack', 'hurt']) {
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
    for (const n of ['idle', 'walk', 'run', 'jump', 'attack', 'hurt']) {
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
  const modelName = glbUrl.split('/').pop();
  const lodName = useForest ? modelName : { '0': 'LOD0', '1': 'LOD1', '2': 'LOD2' }[lodParam] || modelName;
  const clip0 = clips.idle;
  document.getElementById('lodname').textContent = lodName;
  document.getElementById('cliplist').textContent =
    (useForest ? 'Forest_Morning · ' : '') +
    gltf.animations.map((a) => a.name + ' ' + a.duration.toFixed(2) + 's').join(' + ') +
    (hasRun ? ' · Shift = 跑' : ' · Shift = 快走');
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
  takeoffT = 0.18;   // 起跳帧：片段第 0.21 s（原 F13 离地，从第 8 帧起算）÷ 1.15 倍速
  const from = actions[curAnim];
  a.reset();
  a.setLoop(THREE.LoopOnce, 1);
  a.clampWhenFinished = true;
  a.enabled = true;
  a.setEffectiveTimeScale(JUMP_RATE);
  a.setEffectiveWeight(1);
  a.play();
  if (from && from !== a) from.crossFadeTo(a, 0.12, false);
  curAnim = 'jump';
  jumpT = a.getClip().duration / JUMP_RATE;
}

// ---- 战斗：玩家挥击 + 僵尸（动作是 public/models/zombie 下的 Mixamo FBX，占位体格）----
// startup = 挥爪真正伸出去那一刻（源片 F24，裁剪后 0.58 s ÷ 1.45 倍速）
const ATTACK = { startup: 0.19, active: 0.16, recovery: 0.26, reach: 1.9, dot: 0.35, dmg: 20, cd: 0.30, lunge: 2.2 };
const ATK_RATE = 1.10;
let ATK_TOTAL = ATTACK.startup + ATTACK.active + ATTACK.recovery;
const HURT_RATE = 1.9;
let HURT_TOTAL = 0.53;
const SPAWNS = [[4.4, 3.2], [-4.6, 2.8], [1.2, -5.4], [-3.4, -4.8], [5.8, -1.2], [-6.2, -0.6]];
if (params.has('foe')) SPAWNS[0] = params.get('foe').split(',').map(Number);   // ?foe=x,z 截图摆位
const enemies = [];
let enemyAssets = null, wave = 0, waveT = 0;
let hp = 100, hpMax = 100, hurtT = 0, downT = 0, hurtAnimT = 0;
let atkT = 0, atkHit = false, atkCD = 0, atkTotal = 0;   // atkTotal = 本次挥击总时长（有片段用片段长，?noatk 用旧版 0.44 s）

// ---- 成长：等级 / 4 个技能槽 / 升级抽卡 ----
const prog = new Progression();
prog.unlock('ice');                    // 起手只有冰枪，其余三个靠升级卡解锁
let cardQueue = 0;                     // 待选的卡数（一次多杀可能连升数级）
let cardOpen = false;
let cardChoices = [];
const cardsEl = document.getElementById('cards');
const cardRowEl = document.getElementById('cardrow');
const cardTagEl = document.getElementById('cardtag');

function openCards() {
  if (cardQueue <= 0) return;
  cardOpen = true;
  cardChoices = prog.rollCards(3);
  if (!cardsEl) return;
  cardsEl.classList.add('show');
  if (cardTagEl) cardTagEl.textContent = 'LEVEL ' + prog.level + '　·　选一张（按 1 / 2 / 3）';
  cardRowEl.innerHTML = '';
  cardChoices.forEach((card, i) => {
    const { title, desc } = cardText(card);
    const b = document.createElement('button');
    b.className = 'card';
    b.innerHTML = '<span class="n">' + (i + 1) + '</span><b>' + title + '</b><i>' + desc + '</i>';
    b.addEventListener('click', () => chooseCard(i));
    cardRowEl.appendChild(b);
  });
}

function chooseCard(i) {
  if (!cardOpen) return;
  const card = cardChoices[i];
  if (!card) return;
  prog.apply(card);
  cardQueue = Math.max(0, cardQueue - 1);
  cardOpen = false;
  if (cardsEl) cardsEl.classList.remove('show');
  if (cardQueue > 0) openCards();
}

function closeCards() {
  cardOpen = false;
  if (cardsEl) cardsEl.classList.remove('show');
}

function gainXp(kills = 1) {
  if (kills <= 0) return;
  const ups = prog.addKill(kills);
  if (ups > 0) { cardQueue += ups; if (!cardOpen) openCards(); }
}

/** L 键：直接升一级并弹卡；K 键：免费解锁下一个技能（试玩用，不计击杀）。 */
function levelUpByKey() {
  cardQueue += prog.grantLevel();
  if (!cardOpen) openCards();
}

function unlockNextByKey() {
  const next = POOL.find((el) => !prog.has(el));
  return next ? prog.unlock(next) : false;
}

const slotElements = () => prog.slots.map((s) => (s ? s.element : null));

if (params.has('unlock')) {              // ?unlock=1 直接填满 4 槽，供无头截图看技能栏
  for (const el of Object.keys(SKILL_META)) prog.unlock(el);
}
if (params.has('xp')) { prog.xp = parseInt(params.get('xp'), 10) || 0; }
if (params.has('cards')) {               // ?cards=2 直接摆一张选卡界面，供无头截图
  cardQueue = Math.max(1, parseInt(params.get('cards'), 10) || 1);
  openCards();
}

// ---- 技能（demo 的 VFX 管线）：命中结算直接扣僵尸血 ----
const skills = createSkills({
  scene, camera,
  getEnemies: () => enemies,
  radiusOf: ENEMY.radius,
  onHit: (e, killed, element) => {
    vfx.landing(e.root.position.x, e.root.position.y, e.root.position.z, killed ? 1.2 : 0.55);
    if (killed) gainXp(1);
  },
});
skills.resize(window.innerWidth, window.innerHeight);
let skillFrozen = false;

function castSkill(element, force = false) {
  if (!model || cardOpen) return null;
  if (!force && (!grounded || crouched || downT > 0 || hurtAnimT > 0)) return null;
  const dir = new THREE.Vector3(Math.sin(modelYaw), 0, Math.cos(modelYaw));
  const dist = params.has('reach') ? parseFloat(params.get('reach')) : 12;
  skills.setDamageMul(element, prog.damageMul(element));
  const a = skills.cast(element, model.position, dir, dist, prog.cooldownMul(element));
  if (a) dbg('cast ' + element + ' ' + dist + 'm');
  return a;
}

function castSlot(i, force = false) {
  const el = slotElements()[i];
  return el ? castSkill(el, force) : null;
}

function spawnWave() {
  if (!enemyAssets) return;
  const n = Math.min(2 + wave, 8);                       // 无限波：每波多一只，最多 8 只同屏
  const hpScale = 1 + 0.22 * (wave - 1);                  // 每波血量 +22%
  for (let i = 0; i < n; i++) {
    const [sx, sz] = SPAWNS[(wave * 2 + i) % SPAWNS.length];
    const e = new Enemy(enemyAssets, { x: sx, y: world.groundAt(sx, sz, 3), z: sz, hpScale });
    scene.add(e.root);
    enemies.push(e);
  }
  wave++;
}

loadEnemyAssets()
  .then((a) => { enemyAssets = a; spawnWave(); })
  .catch((e) => { console.error('enemy load failed', e); dbg('enemy ERR ' + (e && e.message)); });

function startAttack() {
  if (!model || atkT > 0 || atkCD > 0 || !grounded || crouched || downT > 0 || hurtAnimT > 0) return;
  const a = params.has('noatk') ? null : actions.attack;   // ?noatk=1 退回旧版「无片段 + 弧光」，用于前后对照
  atkTotal = a ? ATK_TOTAL : 0.44;
  atkT = atkTotal;
  atkHit = false;
  atkCD = ATTACK.cd;
  if (!a) return;     // 旧版路径：只靠 update() 里的前冲 + 弧光
  a.reset();
  a.setLoop(THREE.LoopOnce, 1);
  a.clampWhenFinished = true;
  a.enabled = true;
  a.setEffectiveTimeScale(ATK_RATE);
  a.setEffectiveWeight(1);
  a.play();
  const from = actions[curAnim];
  if (from && from !== a) from.crossFadeTo(a, 0.08, false);
  curAnim = 'attack';
}

function attackHit() {
  const fx = Math.sin(modelYaw), fz = Math.cos(modelYaw);
  for (const e of enemies) {
    if (!e.alive) continue;
    const dx = e.root.position.x - model.position.x;
    const dz = e.root.position.z - model.position.z;
    const d = Math.hypot(dx, dz);
    if (d > ATTACK.reach + ENEMY.radius) continue;
    if ((dx * fx + dz * fz) / (d || 1) < ATTACK.dot) continue;   // 只打正面 ±70°
    const killed = e.hurt(ATTACK.dmg, { x: fx, z: fz });
    vfx.landing(e.root.position.x, e.root.position.y, e.root.position.z, killed ? 1.1 : 0.6);
    if (killed) gainXp(1);
  }
}

function hurtPlayer(dmg) {
  if (hurtT > 0 || downT > 0) return;
  hp = Math.max(0, hp - dmg);
  hurtT = 0.6;                                   // 无敌帧，避免被同一记攻击连扣
  const ha = actions.hurt;
  if (ha && atkT <= 0) {                         // 挥击中不打断，其余状态立刻缩一下
    hurtAnimT = HURT_TOTAL;
    ha.reset();
    ha.setLoop(THREE.LoopOnce, 1);
    ha.clampWhenFinished = true;
    ha.enabled = true;
    ha.setEffectiveTimeScale(HURT_RATE);
    ha.setEffectiveWeight(1);
    ha.play();
    const from = actions[curAnim];
    if (from && from !== ha) from.crossFadeTo(ha, 0.05, false);
    curAnim = 'hurt';
  }
  vfx.landing(model.position.x, py, model.position.z, 0.9);
  if (hp <= 0) {
    hp = hpMax;
    downT = 1.4;
    model.position.set(0, 0, 0);
    py = world.groundAt(0, 0, 3); vy = 0; grounded = true;
  }
}


const forward = new THREE.Vector3();
const right = new THREE.Vector3();
const moveDir = new THREE.Vector3();
const camPos = new THREE.Vector3();
const desiredCam = new THREE.Vector3();
const camBase = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);
const tmpQ = new THREE.Quaternion();
let camInit = false;
let speed = 0;


// ---- 玩法状态：重力、跳跃冲量、收集进度 ----
const PLAYER_R = 0.55;
const GRAV = 16.3;
const JUMP_V = 5.4;      // 顶点 0.89 m、滞空 0.66 s：够跳上 0.5 m 一级的箱子，也和 Jump 动作的落地帧对得上
let py = 0, vy = 0, grounded = true, takeoffT = -1, wasGrounded = true;
let collected = 0, playTime = 0, finished = false;
let crouched = false;   // C 键切换：蹲下（这个动作只有下蹲过程，起身用 0.35 s 淡出回站立）
const gameEl = document.getElementById('game');
const flashEl = document.getElementById('flash');
function resetGame() {
  py = 0; vy = 0; grounded = true; takeoffT = -1;
  collected = 0; playTime = 0; finished = false;
  hp = hpMax; hurtT = 0; downT = 0; hurtAnimT = 0; atkT = 0; atkCD = 0; atkHit = false;
  wave = 0; waveT = 0;
  prog.reset(); prog.unlock('ice');
  cardQueue = 0; closeCards();
  for (const e of enemies) if (e.root.parent) e.root.parent.remove(e.root);
  enemies.length = 0;
  spawnWave();
  if (model) { model.position.set(0, 0, 0); modelYaw = 0; }
  for (const o of world.orbs) { o.taken = false; o.mesh.visible = true; o.ring.visible = true; }
}
addEventListener('keydown', (e) => {
  if (e.code === 'KeyR') resetGame();
  if (e.code === 'KeyC' && (actions.crouch || actions.crouchwalk) && grounded) crouched = !crouched;
  if (cardOpen) {                        // 选卡时数字键选牌，其它操作一律锁住
    if (e.code === 'Digit1' || e.code === 'Numpad1') chooseCard(0);
    else if (e.code === 'Digit2' || e.code === 'Numpad2') chooseCard(1);
    else if (e.code === 'Digit3' || e.code === 'Numpad3') chooseCard(2);
    return;
  }
  if (e.code === 'KeyL') levelUpByKey();
  if (e.code === 'KeyK') unlockNextByKey();
  if (e.code === 'KeyJ') startAttack();
  if (e.code === 'Digit1') castSlot(0);
  if (e.code === 'Digit2') castSlot(1);
  if (e.code === 'Digit3') castSlot(2);
  if (e.code === 'Digit4') castSlot(3);
});

function update(dt) {
  if (cardOpen) return;                  // 选卡时整个世界暂停
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
  if (atkT > 0) {
    // 挥击片段独占权重，locomotion 等它播完再接管（结束那一帧由 setAnim 交叉淡出）
  } else if (hurtAnimT > 0) {
    hurtAnimT = Math.max(0, hurtAnimT - dt);
    if (hurtAnimT === 0) { curAnim = 'hurt'; setAnim(want, 0.22); }
  } else if (jumpT > 0) {
    jumpT = Math.max(0, jumpT - dt);
    if (jumpT === 0) { curAnim = 'jump'; setAnim(want); }
  } else setAnim(want, curAnim === 'attack' ? 0.18 : crouched && (want === 'crouch' || want === 'crouchwalk') ? 0.12 : 0.25);
  // 落地即刻切回跑/走，不等跳跃片段的收尾 0.4 s 播完
  if (!wasGrounded && grounded && jumpT > 0.02) { jumpT = 0; curAnim = 'jump'; setAnim(want, 0.18); }
  wasGrounded = grounded;
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
    const impactVy = vy;
    const st = stepVertical({ py, vy, grounded }, dt, GRAV, gh);
    py = st.py; vy = st.vy; grounded = st.grounded;
    model.position.y = py;
    if (!wasGrounded && grounded) {
      vfx.landing(model.position.x, py, model.position.z, THREE.MathUtils.clamp(-impactVy / JUMP_V, 0.35, 1.5));
    }
    const sprinting = grounded && speed > RUN_SPEED * 0.55;
    vfx.trailPoint(model.position.x, py, model.position.z, sprinting);
    if (sprinting && (sprintT -= dt) <= 0) { sprintT = 0.07; vfx.sprintDust(model.position.x, py, model.position.z); }

    // 挥击推进：前冲相位 + 命中窗口（startup 结束那一刻判一次）
    atkCD = Math.max(0, atkCD - dt);
    if (hurtT > 0) hurtT -= dt;
    if (params.has('hurt') && hurtT <= 0 && downT <= 0) hurtPlayer(0);   // ?hurt=1 循环播受击，截图用
    if (downT > 0) downT -= dt;
    if (atkT > 0) {
      atkT = Math.max(0, atkT - dt);
      const el = atkTotal - atkT;
      // 前冲相位；贴到僵尸身上就停住，别冲进去穿模（角色与僵尸之间没有碰撞体）
      let lungeOk = el < ATTACK.startup + ATTACK.active;
      if (lungeOk) {
        for (const e of enemies) {
          if (!e.alive) continue;
          if (Math.hypot(e.root.position.x - model.position.x, e.root.position.z - model.position.z) < ENEMY.radius + PLAYER_R + 0.05) { lungeOk = false; break; }
        }
      }
      if (lungeOk) {
        model.position.x += Math.sin(modelYaw) * ATTACK.lunge * dt;
        model.position.z += Math.cos(modelYaw) * ATTACK.lunge * dt;
        world.resolve(model.position, PLAYER_R, py);
      }
      if (!atkHit && el >= ATTACK.startup) {
        atkHit = true;
        vfx.slash(model.position.x, py, model.position.z, modelYaw);   // 弧光对齐爪子伸出的那一帧
        attackHit();
      }
    }

    if (enemies.length) {
      const pp = { x: model.position.x, y: py, z: model.position.z };
      for (const e of enemies) {
        e.update(dt, pp, world.groundAt, world.resolve);
        if (e.consumeHit()) {
          const dx = model.position.x - e.root.position.x;
          const dz = model.position.z - e.root.position.z;
          if (Math.hypot(dx, dz) <= ENEMY.reach + 0.35) hurtPlayer(ENEMY.dmg);
        }
      }
      if (enemies.every((e) => !e.alive)) {
        waveT += dt;
        if (waveT > 2.2) {                 // 无限波：清场 2.2 s 后刷下一波
          waveT = 0;
          for (const e of enemies) if (e.root.parent) e.root.parent.remove(e.root);
          enemies.length = 0;
          spawnWave();
        }
      }
    }

    if (!finished) {
      picked.length = 0;
      collected += world.tick(dt, performance.now() / 1000, { x: model.position.x, y: py, z: model.position.z }, 1.15, picked);
      for (const orb of picked) vfx.pickup(orb.x, orb.y, orb.z, py);
      playTime += dt;
      if (world.total > 0 && collected >= world.total) { finished = true; jumpT = 0; }
    } else {
      world.tick(dt, performance.now() / 1000, { x: 1e9, y: 0, z: 0 });
    }
    if (gameEl) {
      const alive = enemies.filter((e) => e.alive).length;
      const head = downT > 0 ? '被击倒 · 重生中' : `HP ${Math.round(hp)} / ${hpMax}`;
      gameEl.textContent = finished
        ? `通关！${playTime.toFixed(1)} s · 按 R 重开`
        : `${head} · Lv ${prog.level} ${prog.xp}/${prog.need} · 僵尸 ${alive} · 第 ${Math.max(1, wave)} 波 · 收集 ${collected} / ${world.total} · ${playTime.toFixed(1)} s`;
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
  if (!camInit) { camBase.copy(desiredCam); camInit = true; }
  else camBase.lerp(desiredCam, Math.min(1, dt * 6));
  camera.position.copy(camBase).add(skills.shakeRig.shakeOffset);   // 技能镜头抖动叠在基准位姿上
  camera.lookAt(rig.target);
  camera.rotateZ(skills.shakeRig.shakeRoll);

  if (forestLook && model) {
    forestLook.sun.position.copy(model.position).addScaledVector(forestLook.sunDir, 60);
    forestLook.sun.target.position.copy(model.position);
    forestLook.sun.target.updateMatrixWorld();
    forestLook.sun.shadow.camera.updateProjectionMatrix();
    forestLook.sky.position.copy(camera.position);
    if (atmo && !params.has('still')) atmo.update(dt, model.position);   // ?still=1 冻结雾片漂移，便于逐像素对照
    if (!params.has('still')) sunT += dt;
    if (sunT > 0.1) {          // 太阳缓慢移动：方位 ±20°、仰角 8~14°，光柱与天穹跟着同步
      sunT = 0;
      const t = params.has('sun') ? parseFloat(params.get('sun')) : performance.now() / 1000;   // ?sun= 冻结太阳位置便于对照
      const az = -0.55 + Math.sin(t / 47) * 0.35;
      const el = 0.20 + Math.sin(t / 61) * 0.05;
      const d = new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el)).normalize();
      forestLook.setSunDir(d);
      if (atmo) atmo.setSunDir(d);
      skills.setSunDir(d);
    }
  }
  if (params.has('atk') && model && enemies.length && grounded) {   // ?atk=1 自动连挥，配合 HUD 读数验证状态机
    if (atkT <= 0 && atkCD <= 0) startAttack();
  }
  if (fxDemo && model) {
    const fire = () => {
      const p = model.position;
      if (fxDemo === 'land') vfx.landing(p.x, py, p.z, 1.35);
      else vfx.pickup(p.x + 0.4, py + 1.05, p.z - 1.2, py);
    };
    if (params.has('fxhold')) {          // 定格：先推进到指定相位，之后不再推进
      fire();
      for (let i = 0, n = Math.round(parseFloat(params.get('fxhold')) * 60); i < n; i++) vfx.update(1 / 60);
      fxDemo = null; fxFrozen = true;
    } else if ((fxNext -= dt) <= 0) { fxNext = 0.9; fire(); }
  }
  vfx.update(fxFrozen ? 0 : dt);

  if (skillDemo && model) {                 // ?skill=ice|thunder 自动放一次；&skillhold=<秒> 定格在该相位
    castSkill(skillDemo, true);
    const hold = params.has('skillhold') ? parseFloat(params.get('skillhold')) : null;
    if (hold !== null) { for (let i = 0, n = Math.round(hold * 60); i < n; i++) skills.update(1 / 60); skillFrozen = true; }
    skillDemo = null;
  }
  skills.update(skillFrozen ? 0 : dt);
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
  if (flashEl) {                          // demo 的 ScreenFlash 靠合成 pass 读，这里用一层 DOM 叠色代替
    const f = skills.flash;
    flashEl.style.opacity = f.strength.toFixed(3);
    if (f.strength > 0.001) {
      flashEl.style.backgroundColor = 'rgb(' + Math.round(f.color.r * 255) + ',' + Math.round(f.color.g * 255) + ',' + Math.round(f.color.b * 255) + ')';
    }
  }
  if (mixer && !window.__frozen) mixer.update(dt);

  if (model && stateEl) {
    stateEl.textContent =
      `pos ${model.position.x.toFixed(1)}, ${model.position.z.toFixed(1)} · y ${py.toFixed(2)} · speed ${speed.toFixed(1)} m/s · clip ${(jumpT > 0 ? 'jump' : want).toUpperCase()}${grounded ? '' : ' · 空中'}` +
      (params.has('atk') ? ` · cur ${curAnim} · atkT ${atkT.toFixed(2)} · hit ${atkHit ? 1 : 0}` : '') +
      ((params.has('atk') || params.has('skill')) ? ` · 僵尸 ${enemies.filter((e) => e.alive).length} 活` : '') +
      ` · ${skills.hud(slotElements().filter(Boolean))}`;
  }
}

let acc = 0, frames = 0;
function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  update(dt);
  if (postfx) { postfx.renderDepth(); postfx.render(); }
  else renderer.render(scene, camera);
  frames++; acc += dt;
  if (acc > 0.5) {
    const ri = postfx ? postfx.info : renderer.info.render;   // composer 会重置 info，用 postfx 存下的场景 pass 数值
    statsEl.textContent = `${(frames / acc).toFixed(0)} fps · ${ri.triangles.toLocaleString()} tri · ${ri.calls} draw`;
    frames = 0; acc = 0;
  }
  requestAnimationFrame(tick);
}
tick();

addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  if (postfx) postfx.resize();
  skills.resize(window.innerWidth, window.innerHeight);
});