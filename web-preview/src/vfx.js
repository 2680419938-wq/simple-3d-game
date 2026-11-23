// 事件特效：拾取爆光 / 落地冲击环 + 扬尘 / 冲刺拖尾。
// 条带朝向解法（side = tangent × 指向相机的向量，UV 按弧长参数化）参考 MIT 许可的
// achrefelouafi/LinearAbiltyCastingThreeJS（src/effects/RibbonGeometry.js），按本项目的事件循环重写。
import * as THREE from 'three';

const LAYER = 2;          // 不进 postfx 的深度通道（那趟只渲 layer 0），否则特效会挡光柱
const TRAIL_SEGS = 48;

function radialRing() {
  const s = 256;
  const cv = document.createElement('canvas'); cv.width = cv.height = s;
  const g = cv.getContext('2d');
  const grd = g.createRadialGradient(s / 2, s / 2, s * 0.26, s / 2, s / 2, s * 0.5);
  grd.addColorStop(0.00, 'rgba(255,255,255,0)');
  grd.addColorStop(0.62, 'rgba(255,255,255,0.10)');
  grd.addColorStop(0.84, 'rgba(255,255,255,0.85)');   // 窄亮环，避免糊成一团白雾
  grd.addColorStop(0.93, 'rgba(255,255,255,0.30)');
  grd.addColorStop(1.00, 'rgba(255,255,255,0)');
  g.fillStyle = grd; g.fillRect(0, 0, s, s);
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function radialDot() {
  const s = 128;
  const cv = document.createElement('canvas'); cv.width = cv.height = s;
  const g = cv.getContext('2d');
  const grd = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grd.addColorStop(0.00, 'rgba(255,255,255,0.85)');
  grd.addColorStop(0.45, 'rgba(255,255,255,0.30)');
  grd.addColorStop(1.00, 'rgba(255,255,255,0)');
  g.fillStyle = grd; g.fillRect(0, 0, s, s);
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// 地面扩散光环：平面 + 环形贴图，加色混合，缩放开裂的同时淡出
function makeRingPool(scene, tex, n) {
  const geo = new THREE.PlaneGeometry(2, 2);
  const pool = [];
  for (let i = 0; i < n; i++) {
    const mat = new THREE.MeshBasicMaterial({
      map: tex, transparent: true, opacity: 0, blending: THREE.AdditiveBlending,
      depthWrite: false, side: THREE.DoubleSide, toneMapped: false,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.layers.set(LAYER);
    mesh.visible = false;
    scene.add(mesh);
    pool.push({ mesh, t: 0, life: 0, from: 0.2, to: 1, peak: 1 });
  }
  return pool;
}

// 扬尘：固定容量的 Points，每颗粒子自带寿命，用完的 alpha 归零而不是删除
function makeDust(scene, tex, cap) {
  const pos = new Float32Array(cap * 3);
  const vel = new Float32Array(cap * 3);
  const age = new Float32Array(cap);
  const span = new Float32Array(cap);     // 总寿命
  const alpha = new Float32Array(cap);    // 当前 alpha（着色器属性）
  const size = new Float32Array(cap);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
  geo.setAttribute('aLife', new THREE.BufferAttribute(alpha, 1).setUsage(THREE.DynamicDrawUsage));
  geo.setAttribute('aSize', new THREE.BufferAttribute(size, 1).setUsage(THREE.DynamicDrawUsage));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1000);
  const mat = new THREE.ShaderMaterial({
    uniforms: { uMap: { value: tex }, uColor: { value: new THREE.Color(0xdfe6ea) } },
    vertexShader: `
      attribute float aLife;
      attribute float aSize;
      varying float vLife;
      void main() {
        vLife = aLife;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = aSize * (320.0 / max(0.001, -mv.z));
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      uniform sampler2D uMap;
      uniform vec3 uColor;
      varying float vLife;
      void main() {
        if (vLife <= 0.001) discard;
        float d = texture2D(uMap, gl_PointCoord).a;
        gl_FragColor = vec4(uColor, d * vLife * 0.30);
      }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false,
  });
  const pts = new THREE.Points(geo, mat);
  pts.frustumCulled = false;
  pts.layers.set(LAYER);
  scene.add(pts);
  return { geo, pos, vel, age, span, alpha, size, cap, cursor: 0, alive: 0 };
}

// 冲刺拖尾：预分配三角条带，每帧只重写顶点
class Trail {
  constructor(scene) {
    const vc = (TRAIL_SEGS + 1) * 2;
    this.geo = new THREE.BufferGeometry();
    this.pos = new Float32Array(vc * 3);
    this.uvs = new Float32Array(vc * 2);
    this.side = new Float32Array(vc);
    for (let i = 0; i < vc; i++) this.side[i] = i % 2 ? 1 : -1;
    const idx = new Uint16Array(TRAIL_SEGS * 6);
    for (let s = 0; s < TRAIL_SEGS; s++) {
      const a = s * 2;
      idx.set([a, a + 1, a + 2, a + 2, a + 1, a + 3], s * 6);
    }
    this.geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    this.geo.setAttribute('uv', new THREE.BufferAttribute(this.uvs, 2).setUsage(THREE.DynamicDrawUsage));
    this.geo.setAttribute('aSide', new THREE.BufferAttribute(this.side, 1));
    this.geo.setIndex(new THREE.BufferAttribute(idx, 1));
    this.geo.setDrawRange(0, 0);
    this.geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1000);
    this.mat = new THREE.ShaderMaterial({
      uniforms: { uColor: { value: new THREE.Color(0xa8e4ff) }, uOpacity: { value: 0 } },
      vertexShader: `
        attribute float aSide;
        varying vec2 vUv;
        varying float vSide;
        void main() {
          vUv = uv;
          vSide = aSide;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: `
        uniform vec3 uColor;
        uniform float uOpacity;
        varying vec2 vUv;
        varying float vSide;
        void main() {
          if (uOpacity <= 0.001) discard;
          float across = clamp(1.0 - abs(vSide), 0.0, 1.0);
          // 1.0 - vUv.x 在插值边界会微负（1.0000001），pow(负数, 1.7) = NaN；
          // NaN 像素被 bloom 的低频 mip 抹开后，整屏合成都会变成 NaN → 黑屏。
          float along = pow(clamp(1.0 - vUv.x, 0.0, 1.0), 1.7);
          float a = clamp(across * across * along * uOpacity * 0.60, 0.0, 1.0);
          gl_FragColor = vec4(uColor * (0.45 + 0.35 * along), a);
        }`,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide, toneMapped: false,
    });
    this.mesh = new THREE.Mesh(this.geo, this.mat);
    this.mesh.frustumCulled = false;
    this.mesh.layers.set(LAYER);
    this.mesh.visible = false;
    scene.add(this.mesh);
    this.pts = [];
    this.rise = 0.15;      // 贴地但略高于草丛，否则被草叶按深度切成一段段
    this.width = 1.15;     // 比身体宽，追尾视角才能从两侧看到
    this._tan = new THREE.Vector3();
    this._side = new THREE.Vector3();
    this._view = new THREE.Vector3();
    this._up = new THREE.Vector3(0, 1, 0);
    this._p = new THREE.Vector3();
  }

  push(x, y, z) {
    this.pts.unshift(new THREE.Vector3(x, y + this.rise, z));
    if (this.pts.length > TRAIL_SEGS + 1) this.pts.length = TRAIL_SEGS + 1;
  }

  clear() {
    this.pts.length = 0;
    this.geo.setDrawRange(0, 0);
    this.mat.uniforms.uOpacity.value = 0;
    this.mesh.visible = false;
  }

  build(camera, opacity) {
    const n = this.pts.length;
    this.mat.uniforms.uOpacity.value = opacity;
    if (n < 3 || opacity <= 0.001) { this.mesh.visible = false; return; }
    this.mesh.visible = true;

    const P = this.pts;
    let total = 0;
    for (let i = 1; i < n; i++) total += P[i].distanceTo(P[i - 1]);
    const invTotal = total > 1e-4 ? 1 / total : 0;

    let travelled = 0;
    for (let i = 0; i < n; i++) {
      if (i > 0) travelled += P[i].distanceTo(P[i - 1]);
      const t = travelled * invTotal;

      if (i === 0) this._tan.copy(P[1]).sub(P[0]);
      else if (i === n - 1) this._tan.copy(P[n - 1]).sub(P[n - 2]);
      else this._tan.copy(P[i - 1]).sub(P[i + 1]);      // 头的索引最小，切线指向尾
      if (this._tan.lengthSq() < 1e-10) this._tan.set(0, 0, 1);
      this._tan.normalize();

      // 水平面片：追尾镜头几乎沿切线看，用 view 求 side 会退化成一条线
      this._side.crossVectors(this._tan, this._up);
      if (this._side.lengthSq() < 1e-6) {          // 切线竖直时退回相机朝向
        this._view.copy(camera.position).sub(P[i]);
        this._side.crossVectors(this._tan, this._view);
        if (this._side.lengthSq() < 1e-10) this._side.set(1, 0, 0);
      }
      this._side.normalize();

      const w = this.width * (1 - 0.55 * t);
      const i2 = i * 2;
      this._p.copy(P[i]).addScaledVector(this._side, -w * 0.5);
      this.pos[i2 * 3] = this._p.x; this.pos[i2 * 3 + 1] = this._p.y; this.pos[i2 * 3 + 2] = this._p.z;
      this._p.copy(P[i]).addScaledVector(this._side, w * 0.5);
      this.pos[(i2 + 1) * 3] = this._p.x;
      this.pos[(i2 + 1) * 3 + 1] = this._p.y;
      this.pos[(i2 + 1) * 3 + 2] = this._p.z;

      this.uvs[i2 * 2] = t; this.uvs[i2 * 2 + 1] = 0;
      this.uvs[(i2 + 1) * 2] = t; this.uvs[(i2 + 1) * 2 + 1] = 1;
    }
    this.geo.setDrawRange(0, (n - 1) * 6);
    this.geo.attributes.position.needsUpdate = true;
    this.geo.attributes.uv.needsUpdate = true;
  }
}

export function createVfx(scene, camera) {
  const rings = makeRingPool(scene, radialRing(), 10);
  const dust = makeDust(scene, radialDot(), 120);
  const trail = new Trail(scene);
  let trailOpacity = 0;

  function ring(x, y, z, opts = {}) {
    let e = rings.find((r) => r.t >= r.life);
    if (!e) e = rings.reduce((a, b) => (a.t / a.life > b.t / b.life ? a : b));
    e.mesh.position.set(x, y + 0.02, z);
    e.mesh.material.color.set(opts.color ?? 0x9fe8ff);
    e.t = 0;
    e.life = opts.life ?? 0.5;
    e.from = opts.from ?? 0.25;
    e.to = opts.to ?? 1.7;
    e.peak = opts.peak ?? 0.9;
    e.mesh.visible = true;
  }

  function puff(x, y, z, n, spread, up, sizeK = 1, lifeK = 1) {
    for (let i = 0; i < n; i++) {
      const k = dust.cursor;
      dust.cursor = (dust.cursor + 1) % dust.cap;
      const a = Math.random() * Math.PI * 2;
      const r = Math.random();
      dust.pos[k * 3] = x + Math.cos(a) * r * 0.3;
      dust.pos[k * 3 + 1] = y + 0.05 + Math.random() * 0.14;
      dust.pos[k * 3 + 2] = z + Math.sin(a) * r * 0.3;
      dust.vel[k * 3] = Math.cos(a) * spread * (0.4 + r);
      dust.vel[k * 3 + 1] = up * (0.5 + Math.random());
      dust.vel[k * 3 + 2] = Math.sin(a) * spread * (0.4 + r);
      dust.age[k] = 0;
      dust.span[k] = (0.55 + Math.random() * 0.45) * lifeK;
      dust.size[k] = (0.42 + Math.random() * 0.5) * sizeK;
      dust.alpha[k] = 1;
    }
    dust.geo.attributes.aSize.needsUpdate = true;
  }

  return {
    /** 拾取：地面扩散环（groundY 处）+ 球心一团闪光 + 少量上飘尘 */
    pickup(x, y, z, groundY) {
      ring(x, groundY, z, { color: 0x9fe4ff, from: 0.18, to: 1.5, life: 0.5, peak: 0.85 });
      ring(x, groundY, z, { color: 0xffffff, from: 0.1, to: 0.75, life: 0.28, peak: 0.7 });
      puff(x, y, z, 5, 0.8, 0.8, 0.6, 0.6);
    },
    /** 落地：按冲击强度决定环半径与扬尘量（strength 0..1.5） */
    landing(x, y, z, strength = 1) {
      const s = THREE.MathUtils.clamp(strength, 0.35, 1.5);
      ring(x, y, z, { color: 0xd9c49a, from: 0.22, to: 0.85 + 0.35 * s, life: 0.36, peak: 0.70 });   // 暖土色，和拾取的冷光分开
      puff(x, y, z, Math.round(8 + 10 * s), 1.2 * s, 1.0);
    },
    /** 冲刺时脚步扬尘：每 0.07 s 一撮，向后外侧散开 */
    sprintDust(x, groundY, z) {
      puff(x, groundY + 0.02, z, 2, 0.35, 0.5, 0.55, 0.5);
    },
    /** 每帧喂一个点：running 时拖尾保持不透明度，停下后 0.5 s 内淡出 */
    trailPoint(x, y, z, active) {
      if (active) {
        trail.push(x, y, z);
        trailOpacity = Math.min(1, trailOpacity + 0.16);
      } else {
        trailOpacity = Math.max(0, trailOpacity - 0.055);
        if (trailOpacity <= 0) trail.clear();
      }
    },
    update(dt) {
      for (const e of rings) {
        if (e.t >= e.life) { e.mesh.visible = false; continue; }
        e.t = Math.min(e.life, e.t + dt);
        const k = e.t / e.life;
        e.mesh.scale.setScalar(e.from + (e.to - e.from) * (1 - (1 - k) * (1 - k)));
        e.mesh.material.opacity = e.peak * (1 - k) * (1 - k);
      }

      {
        let alive = 0;
        for (let k = 0; k < dust.cap; k++) {
          if (dust.alpha[k] <= 0) continue;
          dust.age[k] += dt;
          const f = dust.age[k] / dust.span[k];
          if (f >= 1) { dust.alpha[k] = 0; continue; }
          alive++;
          dust.vel[k * 3 + 1] -= 0.9 * dt;
          dust.pos[k * 3] += dust.vel[k * 3] * dt;
          dust.pos[k * 3 + 1] += dust.vel[k * 3 + 1] * dt;
          dust.pos[k * 3 + 2] += dust.vel[k * 3 + 2] * dt;
          dust.vel[k * 3] *= 1 - 2.4 * dt;
          dust.vel[k * 3 + 2] *= 1 - 2.4 * dt;
          dust.alpha[k] = (1 - f) * (1 - f);
        }
        dust.alive = alive;
        dust.geo.attributes.position.needsUpdate = true;
        dust.geo.attributes.aLife.needsUpdate = true;
      }

      trail.build(camera, trailOpacity);
    },
  };
}
