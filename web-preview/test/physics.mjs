
import { stepVertical } from '../src/world.js';
let fails = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const G = 16.3;

// 1) 从 2 m 高落到 0.5 m 台面：应停在 0.5 并接地
{
  const p = { py: 2.0, vy: 0, grounded: false };
  for (let i = 0; i < 200; i++) stepVertical(p, 1 / 60, G, 0.5);
  ok(Math.abs(p.py - 0.5) < 1e-9 && p.grounded && p.vy === 0, 'falls onto 0.5m top and rests (py=' + p.py.toFixed(3) + ')');
}
// 2) 走了 0.5m 台面边缘：台面高度变 0，应该开始下落并最终回到地面
{
  const p = { py: 0.5, vy: 0, grounded: true };
  stepVertical(p, 1 / 60, G, 0);
  ok(p.grounded === false && p.py < 0.5, 'leaving platform starts to fall (py=' + p.py.toFixed(3) + ')');
  for (let i = 0; i < 200; i++) stepVertical(p, 1 / 60, G, 0);
  ok(Math.abs(p.py) < 1e-9 && p.grounded, 'lands back on ground');
}
// 3) 起跳 4.2 m/s：顶点约 0.54 m，滞空约 0.52 s
{
  const p = { py: 0, vy: 5.4, grounded: false };
  let apex = 0, air = 0;
  while (true) {
    stepVertical(p, 1 / 60, G, 0);
    apex = Math.max(apex, p.py); air += 1 / 60;
    if (p.grounded) break;
    if (air > 5) break;
  }
  ok(apex > 0.80 && apex < 0.95, 'jump apex ' + apex.toFixed(3) + ' m');
  ok(air > 0.60 && air < 0.72, 'air time ' + air.toFixed(2) + ' s');
}
console.log(fails ? '\n' + fails + ' FAILED' : '\nALL PASS');
process.exit(fails ? 1 : 0);
