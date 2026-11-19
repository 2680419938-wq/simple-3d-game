// 关卡逻辑的确定性测试：碰撞、踩台面、拾取。运行：node test/world.mjs
import { createWorld } from '../src/world.js';

const w = createWorld({ add() {} });
const R = 0.55;
let fails = 0;
const ok = (cond, msg) => { console.log((cond ? 'PASS ' : 'FAIL ') + msg); if (!cond) fails++; };
const near = (a, b, tol = 0.06) => Math.abs(a - b) <= tol;

// 1) 从原点沿 -z 撞向 (0,-5.2) 的矮墙：6.0 x 0.9 x 0.9，近侧沿 z=-4.75
{
  const p = { x: 0, y: 0, z: 0 };
  for (let i = 0; i < 300; i++) { p.z -= 5.3 / 60; w.resolve(p, R, 0); }
  ok(near(p.z, -4.75 + R), 'walk-into 0.9m wall stops at z=' + p.z.toFixed(2) + ' (expect ' + (-4.75 + R).toFixed(2) + ')');
}
// 2) 沿 +x 走到边界墙（内沿 x=9.7）
{
  const p = { x: 0, y: 0, z: 0 };
  for (let i = 0; i < 800; i++) { p.x += 5.3 / 60; w.resolve(p, R, 0); }
  ok(near(p.x, 9.7 - R, 0.08), 'boundary wall stops at x=' + p.x.toFixed(2) + ' (expect ' + (9.7 - R).toFixed(2) + ')');
}
// 3) 台面高度：站在地面时不会被吸上 0.5m 箱顶；跳起来能站
{
  const atGround = w.groundAt(4.2, 4.2, 0);
  const atTop = w.groundAt(4.2, 4.2, 0.5);
  ok(atGround === 0, 'ground level ignores 0.5m crate top (got ' + atGround + ')');
  ok(near(atTop, 0.5, 1e-6), 'standing at 0.5m keeps crate top (got ' + atTop + ')');
}
// 4) 1.6m 高台：从上方落下能站住，从地面不算
{
  ok(w.groundAt(-4.4, 3.0, 0) === 0, '1.6m platform not walkable from ground');
  ok(near(w.groundAt(-4.4, 3.0, 1.6), 1.6, 1e-6), '1.6m platform holds when above it');
}
// 5) 空中不再被箱侧推挤（y 高于顶面时允许通过）
{
  const p = { x: 4.2, y: 0, z: 4.2 };
  w.resolve(p, R, 0.7);
  ok(near(p.x, 4.2, 1e-6) && near(p.z, 4.2, 1e-6), 'no side push when above crate top');
}
// 6) 拾取与去重
{
  const o = w.orbs[0];
  const got = w.tick(0.016, 0, { x: o.x, y: o.base - 1.0, z: o.z }, 1.15);
  ok(got === 1 && o.taken === true, 'pickup counts once (got ' + got + ')');
  ok(w.tick(0.016, 0, { x: o.x, y: o.base - 1.0, z: o.z }, 1.15) === 0, 'same orb not counted twice');
  const far = w.orbs[1];
  ok(w.tick(0.016, 0, { x: far.x + 4, y: 0, z: far.z }, 1.15) === 0, 'far orb not picked');
  ok(w.total === 12 && w.orbs.length === 12, 'orb count = ' + w.total);
}
console.log(fails ? '\n' + fails + ' FAILED' : '\nALL PASS');
process.exit(fails ? 1 : 0);
