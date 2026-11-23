// 大气：太阳光柱（交叉面片，带场景深度软遮挡）+ 贴地雾层（缓慢漂移的水平雾片），全程序化贴图。
import * as THREE from 'three';

const VS = [
  'varying vec2 vUv; varying float vDist;',
  'void main() {',
  '  vUv = uv;',
  '  vec4 mv = modelViewMatrix * vec4(position, 1.0);',
  '  vDist = -mv.z;',
  '  gl_Position = projectionMatrix * mv;',
  '}',
].join('\n');

// 深度图里存的是窗口深度，线性化成「到相机的距离」，再和当前片元比较：
// 片元在几何体后面 -> 0（被挡住），刚好贴在其前面 -> 逐渐显现。这就是软粒子写法。
const FS = [
  'uniform sampler2D tMap;',
  'uniform sampler2D tDepth;',
  'uniform vec2 uRes;',
  'uniform float uNear; uniform float uFar;',
  'uniform vec3 uColor; uniform float uOpacity; uniform float uSoft;',
  'varying vec2 vUv; varying float vDist;',
  'void main() {',
  '  vec4 tex = texture2D(tMap, vUv);',
  '  float d = texture2D(tDepth, gl_FragCoord.xy / uRes).x;',
  '  float sceneDist = -uNear * uFar / ((uFar - uNear) * d - uFar);',
  '  float occ = clamp((sceneDist - vDist) / uSoft, 0.0, 1.0);',
  '  gl_FragColor = vec4(uColor, tex.a * uOpacity * occ);',
  '}',
].join('\n');

function shaftTexture() {
  const c = document.createElement('canvas');
  c.width = 32; c.height = 256;
  const g = c.getContext('2d');
  const grd = g.createLinearGradient(0, 0, 0, 256);
  grd.addColorStop(0.0, 'rgba(255,255,255,0)');
  grd.addColorStop(0.25, 'rgba(255,255,255,0.55)');
  grd.addColorStop(0.65, 'rgba(255,255,255,0.85)');
  grd.addColorStop(1.0, 'rgba(255,255,255,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, 32, 256);
  const side = g.createLinearGradient(0, 0, 32, 0);
  side.addColorStop(0, 'rgba(0,0,0,0.9)');
  side.addColorStop(0.5, 'rgba(0,0,0,0)');
  side.addColorStop(1, 'rgba(0,0,0,0.9)');
  g.globalCompositeOperation = 'destination-out';
  g.fillStyle = side;
  g.fillRect(0, 0, 32, 256);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  return t;
}

function fogTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = 'rgba(0,0,0,0)';
  g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 150; i++) {
    const x = Math.random() * 256, y = Math.random() * 256;
    const r = 26 + Math.random() * 70;
    const grd = g.createRadialGradient(x, y, 0, x, y, r);
    const a = 0.05 + Math.random() * 0.07;
    grd.addColorStop(0, 'rgba(255,255,255,' + a.toFixed(3) + ')');
    grd.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grd;
    g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

// 无深度图时的兜底：1x1 全远深度，等价于「不做遮挡」（用于 ?soft=0 对照）
function farDepthTexture() {
  const t = new THREE.DataTexture(new Uint8Array([255]), 1, 1, THREE.RedFormat);
  t.magFilter = t.minFilter = THREE.NearestFilter;
  t.needsUpdate = true;
  return t;
}

export function addAtmo(scene, sunDir, depthSrc, opts = {}) {
  const scale = opts.scale ?? 1.0;    // 纯倍数；绝对亮度由调用方给的基准值决定（main.js 里的 ATMO_SCALE）
  const farTex = farDepthTexture();
  const group = new THREE.Group();
  scene.add(group);
  group.layers.set(1);
  const mats = [];

  function material({ map, color, opacity, additive, soft }) {
    const m = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
      uniforms: {
        tMap: { value: map },
        tDepth: { value: depthSrc ? depthSrc.texture : farTex },
        uRes: { value: new THREE.Vector2(1, 1) },
        uNear: { value: 0.1 }, uFar: { value: 520 },
        uColor: { value: new THREE.Color(color) },
        uOpacity: { value: opacity * scale },
        uSoft: { value: soft },
      },
      vertexShader: VS,
      fragmentShader: FS,
    });
    mats.push(m);
    return m;
  }

  // --- 光柱：每根两根交叉面片，沿太阳方向倾斜 ---
  const tex = shaftTexture();
  const dir = sunDir.clone().normalize().negate();      // 光线行进方向（从太阳射向地面）
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
  const shafts = [];
  for (let i = 0; i < 12; i++) {
    const g = new THREE.PlaneGeometry(1.1 + Math.random() * 1.6, 14 + Math.random() * 10);
    const mat = material({ map: tex, color: 0xffe9c8, opacity: 0.14, additive: true, soft: 1.4 });
    const m1 = new THREE.Mesh(g, mat);
    const m2 = new THREE.Mesh(g, mat);
    m2.rotation.z = Math.PI / 2;
    m1.add(m2);
    m1.quaternion.copy(q);
    m1.position.set((Math.random() - 0.5) * 46, 4 + Math.random() * 4, (Math.random() - 0.5) * 46);
    m1.userData = { ox: m1.position.x, oz: m1.position.z, ph: Math.random() * 6.28, sp: 0.08 + Math.random() * 0.12, base: 0.14 * scale };
    m1.layers.set(1);
    m2.layers.set(1);
    group.add(m1);
    shafts.push(m1);
  }

  // --- 贴地雾：三层水平雾片，缓慢漂移 ---
  const fogTex = [fogTexture(), fogTexture(), fogTexture()];
  const layers = [];
  for (let i = 0; i < 3; i++) {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(150, 150).rotateX(-Math.PI / 2),
      material({ map: fogTex[i], color: 0xe8e3d2, opacity: 0.085 + i * 0.03, additive: false, soft: 1.2 })
    );
    m.position.y = 0.18 + i * 0.34;
    m.userData = { t: 0, sp: 0.004 + i * 0.002 };
    m.layers.set(1);
    scene.add(m);
    layers.push(m);
  }

  function syncDepth() {
    if (!depthSrc) return;   // soft=0：深度图永远是「全远」，occ 恒为 1
    for (const m of mats) {
      m.uniforms.tDepth.value = depthSrc.texture;
      m.uniforms.uRes.value.copy(depthSrc.res);
      m.uniforms.uNear.value = depthSrc.near;
      m.uniforms.uFar.value = depthSrc.far;
    }
  }

  return {
    setSunDir(d) {
      const q2 = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize().negate());
      for (const s of shafts) s.quaternion.copy(q2);
    },
    update(dt, focus) {
      syncDepth();
      for (const s of shafts) {
        s.userData.t = (s.userData.t || 0) + dt * s.userData.sp;
        s.position.x = s.userData.ox + Math.sin(s.userData.t + s.userData.ph) * 1.6;
        s.position.z = s.userData.oz + Math.cos(s.userData.t * 0.7 + s.userData.ph) * 1.6;
        const w = 0.10 + 0.07 * Math.sin(s.userData.t * 1.7 + s.userData.ph);
        s.material.uniforms.uOpacity.value = Math.max(0.02, s.userData.base + w * scale);
      }
      for (const l of layers) {
        l.userData.t += dt * l.userData.sp;
        l.material.uniforms.tMap.value.offset.set(l.userData.t * 0.35, l.userData.t * 0.42);
      }
      if (focus) group.position.set(focus.x, 0, focus.z);
    },
  };
}