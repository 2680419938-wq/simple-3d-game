
// 关卡与玩法：木箱障碍、可站立的平台、收集球、边界墙。
// 碰撞是纯 XZ 圆 vs AABB + 顶面高度，够原型用。
import * as THREE from 'three';

/** 竖直方向积分：只负责 py/vy/grounded，落地判定用传入的台面高度 */
export function stepVertical(p, dt, g, gh) {
  p.vy -= g * dt;
  p.py += p.vy * dt;
  if (p.py <= gh) { p.py = gh; p.vy = 0; p.grounded = true; }
  else p.grounded = false;
  return p;
}

export function createWorld(scene, opts = {}) {
  const useArena = opts.arena !== false;
  const useOrbs = opts.orbs !== false;
  const colliders = [];   // { minx, maxx, minz, maxz, top }
  const orbs = [];
  const group = new THREE.Group();
  scene.add(group);

  const crateMat = new THREE.MeshStandardMaterial({ color: 0x39485b, roughness: 0.88, metalness: 0.06 });
  const padMat = new THREE.MeshStandardMaterial({ color: 0x2f3d4e, roughness: 0.9, metalness: 0.04 });
  const edgeMat = new THREE.LineBasicMaterial({ color: 0x7e9bc0, transparent: true, opacity: 0.45 });
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x1d2530, roughness: 0.95, metalness: 0.02 });

  function block(x, z, w, h, d, mat = crateMat, solid = true) {
    const geo = new THREE.BoxGeometry(w, h, d);
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, h / 2, z);
    m.castShadow = true; m.receiveShadow = true;
    group.add(m);
    if (mat !== wallMat) {
      const e = new THREE.LineSegments(new THREE.EdgesGeometry(geo), edgeMat);
      e.position.copy(m.position);
      group.add(e);
    }
    if (solid) colliders.push({ minx: x - w / 2, maxx: x + w / 2, minz: z - d / 2, maxz: z + d / 2, top: h });
    return m;
  }

  // 边界墙（20x20 的场子）
  const R = 10, T = 0.6, H = 3;
  if (useArena) {
  block(0, -R, 2 * R + T, H, T, wallMat);
  block(0, R, 2 * R + T, H, T, wallMat);
  block(-R, 0, T, H, 2 * R + T, wallMat);
  block(R, 0, T, H, 2 * R + T, wallMat);

  // 平台 / 台阶：给「跳上去」留出可玩的层次
  block(4.2, 4.2, 2.6, 0.5, 2.6);
  block(4.6, 1.7, 1.8, 1.0, 1.8);
  block(-4.4, 3.0, 2.2, 1.6, 2.2, padMat);
  block(-1.0, 6.0, 1.8, 0.45, 1.8);
  block(1.0, 6.2, 1.8, 0.9, 1.8);
  block(3.0, 6.2, 1.8, 1.35, 1.8);
  block(0.0, -5.2, 6.0, 0.9, 0.9);
  block(-5.6, -3.6, 1.2, 2.4, 1.2, padMat);
  // 通往 1.6 m 高台的梯级：0 → 0.5 → 1.05 → 1.6，限高跳跃 0.89 m 刚好够
  block(-1.4, 3.0, 1.2, 0.5, 1.2);
  block(-2.8, 3.0, 1.4, 1.05, 1.4);
  block(6.4, -4.4, 1.4, 0.7, 1.4);
  }

  // 收集球：地面一圈 + 平台顶
  const orbMat = new THREE.MeshBasicMaterial({ color: 0x9df4ff, toneMapped: false });
  const orbGeo = new THREE.IcosahedronGeometry(0.24, 0);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0x6fe3ff, transparent: true, opacity: 0.3, side: THREE.DoubleSide, toneMapped: false });
  function orb(x, y, z) {
    const m = new THREE.Mesh(orbGeo, orbMat);
    m.position.set(x, y, z);
    group.add(m);
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.34, 0.42, 24), ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(x, 0.012, z);
    group.add(ring);
    orbs.push({ mesh: m, ring, base: y, taken: false, x, z });
  }
  if (useOrbs) {
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + 0.4;
    orb(Math.cos(a) * 6.6, 0.55, Math.sin(a) * 6.6);
  }
  orb(4.2, 0.5 + 0.55, 4.2);
  orb(4.6, 1.0 + 0.55, 1.7);
  orb(-4.4, 1.6 + 0.55, 3.0);
  orb(-1.0, 0.45 + 0.55, 6.0);
  orb(1.0, 0.9 + 0.55, 6.2);
  orb(3.0, 1.35 + 0.55, 6.2);
  }

  return {
    colliders,
    orbs,
    get total() { return orbs.length; },
    addBoxes(list) { for (const b of list) colliders.push(b); },
    addOrbs(pts) { for (const p of pts) orb(p[0], p[1] === undefined ? 0.55 : p[1], p[2]); },
    /** 当前位置可站立的最高面（低于脚上方 0.4 m 的顶面才算） */
    groundAt(x, z, y) {
      let best = 0;
      for (const c of colliders) {
        if (x < c.minx - 0.25 || x > c.maxx + 0.25) continue;
        if (z < c.minz - 0.25 || z > c.maxz + 0.25) continue;
        if (c.top > y + 0.4) continue;
        if (c.top > best) best = c.top;
      }
      return best;
    },
    /** 把玩家圆推出实心方块；返回 true 表示撞到了 */
    resolve(pos, radius, y) {
      let hit = false;
      for (const c of colliders) {
        if (y >= c.top - 0.06) continue;           // 站在顶上或已高过顶面，不算撞
        const cx = Math.max(c.minx, Math.min(pos.x, c.maxx));
        const cz = Math.max(c.minz, Math.min(pos.z, c.maxz));
        let dx = pos.x - cx, dz = pos.z - cz;
        const d2 = dx * dx + dz * dz;
        if (d2 > radius * radius) continue;
        hit = true;
        if (d2 > 1e-8) {
          const d = Math.sqrt(d2), push = radius - d;
          pos.x += (dx / d) * push; pos.z += (dz / d) * push;
        } else {                                    // 圆心在方块里：沿最小穿透轴推出
          const px = Math.min(pos.x - c.minx, c.maxx - pos.x);
          const pz = Math.min(pos.z - c.minz, c.maxz - pos.z);
          if (px < pz) pos.x += (pos.x - (c.minx + c.maxx) / 2 > 0 ? 1 : -1) * (px + radius);
          else pos.z += (pos.z - (c.minz + c.maxz) / 2 > 0 ? 1 : -1) * (pz + radius);
        }
      }
      return hit;
    },
    /** 拾取 + 球体浮动动画；返回本次收集数量，收集到的球位置可选追加到 out（供特效使用） */
    tick(dt, t, playerPos, radius = 1.15, out = null) {
      let got = 0;
      for (const o of orbs) {
        if (o.taken) continue;
        o.mesh.position.y = o.base + Math.sin(t * 2.2 + o.x) * 0.07;
        o.mesh.rotation.y += dt * 1.6;
        const dx = playerPos.x - o.x, dz = playerPos.z - o.z;
        const dy = playerPos.y + 1.0 - o.mesh.position.y;
        if (dx * dx + dz * dz + dy * dy * 0.35 < radius * radius) {
          o.taken = true;
          got++;
          if (out) out.push({ x: o.mesh.position.x, y: o.mesh.position.y, z: o.mesh.position.z });
          o.mesh.visible = false; o.ring.visible = false;
        }
      }
      return got;
    },
  };
}
