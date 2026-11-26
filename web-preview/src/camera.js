// 第三人称相机的遮挡距离计算（纯数学，不 import three，node 可直接测）。
// world.colliders 的盒体是 { minx, maxx, minz, maxz, top }，底面恒为 y=0。

/** 射线（单位方向 dir.x/y/z）与 AABB 求交，返回进入距离；无交返回 null，起点在盒内返回约 0。 */
export function rayBox(ox, oy, oz, dir, c, r = 0) {
  const o = [ox, oy, oz];
  const d = [dir.x, dir.y, dir.z];
  const lo = [c.minx - r, -r, c.minz - r];
  const hi = [c.maxx + r, c.top + r, c.maxz + r];
  let tmin = 1e-4;
  let tmax = Infinity;
  for (let i = 0; i < 3; i++) {
    if (Math.abs(d[i]) < 1e-6) {
      if (o[i] < lo[i] || o[i] > hi[i]) return null;
      continue;
    }
    let t1 = (lo[i] - o[i]) / d[i];
    let t2 = (hi[i] - o[i]) / d[i];
    if (t1 > t2) { const t = t1; t1 = t2; t2 = t; }
    if (t1 > tmin) tmin = t1;
    if (t2 < tmax) tmax = t2;
    if (tmin > tmax) return null;
  }
  return tmin;
}

/**
 * 目标点到相机方向上可用的距离：撞到树干/箱体就在命中处截断。
 * minTop 用来忽略矮箱子——站在上面时它的顶面不该把镜头顶到角色背上。
 */
/** 把角度规整到 (−π, π]，避免插值绕远路。 */
export function wrapAngle(a) {
  let x = (a + Math.PI) % (Math.PI * 2);
  if (x < 0) x += Math.PI * 2;
  return x - Math.PI;
}

/** 相机 yaw 转到「从背后看向 (tx,tz)」需要的角度：forward = (−sin yaw, 0, −cos yaw)。 */
export function yawToLookAt(px, pz, tx, tz) {
  return Math.atan2(-(tx - px), -(tz - pz));
}

/** 朝目标角转 maxStep 弧度（走最短弧），不越过目标。 */
export function approachAngle(cur, target, maxStep) {
  const d = wrapAngle(target - cur);
  if (Math.abs(d) <= maxStep) return target;
  return cur + Math.sign(d) * maxStep;
}

export function clearDistance(origin, dir, colliders, maxDist, { radius = 0.3, minTop = 1.4, pad = 0.12 } = {}) {
  let best = maxDist;
  let blocked = false;
  for (const c of colliders) {
    if (c.top < minTop) continue;
    const t = rayBox(origin.x, origin.y, origin.z, dir, c, radius);
    if (t !== null && t < best) { best = t; blocked = true; }
  }
  return blocked ? best - pad : maxDist;   // 没被挡就原样返回，别凭空缩 12 cm
}
