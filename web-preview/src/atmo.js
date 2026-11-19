
// 大气：太阳光柱（交叉面片）+ 贴地雾层（缓慢漂移的水平雾片），全程序化生成贴图。
import * as THREE from 'three';

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

export function addAtmo(scene, sunDir) {
  const group = new THREE.Group();
  scene.add(group);

  // --- 光柱：每根两根交叉面片，沿太阳方向倾斜 ---
  const tex = shaftTexture();
  const dir = sunDir.clone().normalize().negate();      // 光线行进方向（从太阳射向地面）
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
  const shafts = [];
  const mat0 = new THREE.MeshBasicMaterial({
    map: tex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    color: 0xffe9c8, opacity: 0.22, side: THREE.DoubleSide, toneMapped: false,
  });
  for (let i = 0; i < 12; i++) {
    const g = new THREE.PlaneGeometry(1.1 + Math.random() * 1.6, 14 + Math.random() * 10);
    const m1 = new THREE.Mesh(g, mat0);
    const m2 = new THREE.Mesh(g, mat0);
    m2.rotation.z = Math.PI / 2;
    m1.add(m2);
    m1.quaternion.copy(q);
    m1.position.set((Math.random() - 0.5) * 46, 4 + Math.random() * 4, (Math.random() - 0.5) * 46);
    m1.userData = { ox: m1.position.x, oz: m1.position.z, ph: Math.random() * 6.28, sp: 0.08 + Math.random() * 0.12 };
    group.add(m1);
    shafts.push(m1);
  }

  // --- 贴地雾：三层水平雾片，缓慢漂移 ---
  const fogTex = [fogTexture(), fogTexture(), fogTexture()];
  const layers = [];
  for (let i = 0; i < 3; i++) {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(150, 150).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({
        map: fogTex[i], transparent: true, depthWrite: false, color: 0xe4ebef,
        opacity: 0.10 + i * 0.03, toneMapped: false,
      })
    );
    m.position.y = 0.22 + i * 0.42;
    m.userData = { t: 0, sp: 0.004 + i * 0.002 };
    scene.add(m);
    layers.push(m);
  }

  return {
    update(dt, focus) {
      for (const s of shafts) {
        s.userData.t = (s.userData.t || 0) + dt * s.userData.sp;
        s.position.x = s.userData.ox + Math.sin(s.userData.t + s.userData.ph) * 1.6;
        s.position.z = s.userData.oz + Math.cos(s.userData.t * 0.7 + s.userData.ph) * 1.6;
        const w = 0.13 + 0.08 * Math.sin(s.userData.t * 1.7 + s.userData.ph);
        s.children[0].material.opacity = Math.max(0.05, 0.20 + w);
      }
      for (const l of layers) {
        l.userData.t += dt * l.userData.sp;
        l.material.map.offset.set(l.userData.t * 0.35, l.userData.t * 0.42);
      }
      if (focus) group.position.set(focus.x, 0, focus.z);
    },
  };
}
