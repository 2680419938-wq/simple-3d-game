import { rayBox, clearDistance, wrapAngle, yawToLookAt, approachAngle } from '../src/camera.js';

let pass = 0, fail = 0;
const ok = (name, cond, extra = '') => {
  if (cond) { pass++; console.log('PASS ' + name); }
  else { fail++; console.log('FAIL ' + name + (extra ? ' — ' + extra : '')); }
};
const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;

const origin = { x: 0, y: 1.45, z: 0 };
const dir = { x: 0, y: 0, z: 1 };                 // 相机在目标点 +Z 方向
const trunk = { minx: -0.4, maxx: 0.4, minz: 4.6, maxz: 5.4, top: 6 };   // 近面 4.6 m
const crate = { minx: -0.6, maxx: 0.6, minz: 3.0, maxz: 4.2, top: 1.0 }; // 矮箱：不该挡镜头

ok('open space keeps the wanted distance', clearDistance(origin, dir, [], 6) === 6);
ok('trunk truncates at its near face', near(clearDistance(origin, dir, [trunk], 6), 4.6 - 0.3 - 0.12), String(clearDistance(origin, dir, [trunk], 6)));
ok('trunk beyond the wanted distance is ignored', clearDistance(origin, dir, [trunk], 3) === 3);
ok('low crate does not block the camera', clearDistance(origin, dir, [crate], 6) === 6);
ok('same crate blocks a low camera when minTop is lowered', clearDistance({ x: 0, y: 0.8, z: 0 }, dir, [crate], 6, { minTop: 0.5 }) < 6);
ok('blocker behind the target is ignored', clearDistance(origin, { x: 0, y: 0, z: -1 }, [crate], 6) === 6);

const side = { minx: 3, maxx: 3.8, minz: 4.6, maxz: 5.4, top: 6 };
ok('off-axis trunk is ignored', clearDistance(origin, dir, [side], 6) === 6);
const diag = { x: Math.SQRT1_2, y: 0, z: Math.SQRT1_2 };
ok('diagonal ray misses a trunk that is not on the line', clearDistance(origin, diag, [side], 8) === 8);
const onLine = { minx: 3, maxx: 3.8, minz: 3, maxz: 3.8, top: 6 };
ok('diagonal ray hits a trunk on the line', near(clearDistance(origin, diag, [onLine], 12), (3 - 0.3) / Math.SQRT1_2 - 0.12, 1e-9), String(clearDistance(origin, diag, [onLine], 12)));

const a = clearDistance(origin, dir, [trunk], 6, { radius: 0.3 });
const b = clearDistance(origin, dir, [trunk], 6, { radius: 0.6 });
ok('bigger camera radius truncates earlier', b < a, a + ' vs ' + b);

ok('ray starting inside the box reports ~0', rayBox(0, 1, 5, dir, trunk, 0.3) < 0.01);
ok('camera distance is clamped by the caller when inside a trunk', clearDistance(0 && origin, dir, [trunk], 6) <= 6);

const far = { minx: -0.4, maxx: 0.4, minz: 8.0, maxz: 8.8, top: 6 };
ok('nearest blocker wins', near(clearDistance(origin, dir, [far, trunk], 10), 4.6 - 0.42));

// 仰视时射线朝上，树干底部不该误挡
const up = { x: 0, y: 0.5, z: 0.866 };
ok('looking up over a short trunk is clear', clearDistance(origin, up, [{ minx: -0.4, maxx: 0.4, minz: 0.6, maxz: 1.4, top: 0.5 }], 6) === 6);
ok('looking up into a tall trunk is blocked', clearDistance(origin, up, [{ minx: -0.4, maxx: 0.4, minz: 0.6, maxz: 1.4, top: 6 }], 6) < 6);

// ---- 软锁定：yaw 数学 ----
const PI = Math.PI, EPS = 1e-9;
ok('wrapAngle maps pi to pi', near(Math.abs(wrapAngle(PI)), PI, 1e-9), String(wrapAngle(PI)));
ok('wrapAngle maps 3pi to pi', near(Math.abs(wrapAngle(3 * PI)), PI, 1e-9));
ok('wrapAngle unwraps 2pi offsets', near(wrapAngle(0.3 + 2 * PI), 0.3, 1e-9));

// forward = (−sin yaw, 0, −cos yaw)：yaw=0 时相机在 +Z，forward 指向 −Z
ok('yaw 0 looks toward -Z', near(yawToLookAt(0, 0, 0, -5), 0, 1e-9), String(yawToLookAt(0, 0, 0, -5)));
ok('yaw pi/2 looks toward -X', near(yawToLookAt(0, 0, -5, 0), PI / 2, 1e-9), String(yawToLookAt(0, 0, -5, 0)));
ok('yaw -pi/2 looks toward +X', near(yawToLookAt(0, 0, 5, 0), -PI / 2, 1e-9), String(yawToLookAt(0, 0, 5, 0)));
// 与 forward 公式自洽：用得到的 yaw 算 forward，应指向目标
{
  const yaw = yawToLookAt(2, 3, 5, 7);
  const fx = -Math.sin(yaw), fz = -Math.cos(yaw);
  const dx = 5 - 2, dz = 7 - 3, len = Math.hypot(dx, dz);
  ok('yawToLookAt agrees with the forward formula', near(fx, dx / len, 1e-9) && near(fz, dz / len, 1e-9));
}

ok('approachAngle snaps when inside the step', approachAngle(0.1, 0.15, 0.1) === 0.15);
ok('approachAngle steps toward the target', near(approachAngle(0, 1, 0.2), 0.2, 1e-9));
ok('approachAngle steps backwards', near(approachAngle(1, 0, 0.2), 0.8, 1e-9));
ok('approachAngle takes the short way around pi', near(wrapAngle(approachAngle(3.0, -3.0, 0.1) - 3.0), 0.1, 1e-9), String(approachAngle(3.0, -3.0, 0.1)));
// 从 3.0 转到 −3.0 走 +0.3 的短弧（不是 −6.0 的长弧）
ok('approachAngle never overshoots', Math.abs(wrapAngle(approachAngle(0, 0.05, 1) - 0.05)) < 1e-12);

console.log(pass + ' PASS, ' + fail + ' FAIL');
process.exit(fail ? 1 : 0);
