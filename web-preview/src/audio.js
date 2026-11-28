// 程序化音效：全部用 WebAudio 现场合成，仓库里不带任何音频文件。
// 纯函数（表 + 衰减/声像）可被 node 直接测；发声部分在没有 AudioContext 的地方自动变成空操作。

export const SOUNDS = {
  jump:        { dur: 0.22, gain: 0.46 },
  land:        { dur: 0.30, gain: 0.55 },
  step:        { dur: 0.10, gain: 0.28 },
  swing:       { dur: 0.24, gain: 0.42 },
  hit:         { dur: 0.28, gain: 0.62 },
  hurt:        { dur: 0.40, gain: 0.60 },
  die:         { dur: 0.90, gain: 0.55 },
  growl:       { dur: 0.55, gain: 0.42 },
  pickup:      { dur: 0.45, gain: 0.38 },
  levelup:     { dur: 0.85, gain: 0.40 },
  click:       { dur: 0.10, gain: 0.32 },
  cast_ice:    { dur: 0.85, gain: 0.50 },
  cast_thunder:{ dur: 0.95, gain: 0.55 },
  cast_beam:   { dur: 0.90, gain: 0.50 },
  cast_phoenix:{ dur: 1.00, gain: 0.55 },
  impact_ice:  { dur: 0.70, gain: 0.60 },
  impact_thunder: { dur: 0.90, gain: 0.62 },
  impact_beam: { dur: 0.80, gain: 0.58 },
  impact_phoenix: { dur: 0.90, gain: 0.60 },
};

/** 元素 → 施法/命中音效名 */
export function castSound(element) { return SOUNDS['cast_' + element] ? 'cast_' + element : 'swing'; }
export function impactSound(element) { return SOUNDS['impact_' + element] ? 'impact_' + element : 'hit'; }

/** 距离衰减：8 m 内基本不降，20 m 外几乎听不见 */
export function attenuation(dist) { return 1 / (1 + Math.max(0, dist) * 0.09); }

/** 左右声像：把听者坐标系里的 dx 投到 ±1（|dx| = 12 m 时到满） */
export function panFor(dx) { return Math.max(-1, Math.min(1, dx / 12)); }

/** 同名音效最多同时几只，防止一屏僵尸同时倒地糊成噪音 */
export const VOICES = { land: 2, hit: 4, growl: 3, die: 4, step: 2, pickup: 3 };

function noiseBuffer(ctx, seconds = 2) {
  const n = Math.floor(ctx.sampleRate * seconds);
  const buf = ctx.createBuffer(1, n, ctx.sampleRate);
  const d = buf.getChannelData(0);
  let seed = 22695477;
  for (let i = 0; i < n; i++) {              // 固定种子：每次启动噪声一致，便于对比音色
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    d[i] = (seed / 0x3fffffff) - 1;
  }
  return buf;
}

function env(ctx, t, { a = 0.005, d = 0.2, peak = 0.5, floor = 0.0001 }) {
  const g = ctx.createGain();
  g.gain.setValueAtTime(floor, t);
  g.gain.linearRampToValueAtTime(peak, t + a);
  g.gain.exponentialRampToValueAtTime(floor, t + a + d);
  return g;
}

function noise(ctx, t, { dur = 0.2, freq = 1200, q = 1, type = 'bandpass', peak = 0.4, sweep = 0, buf }) {
  const src = ctx.createBufferSource();
  src.buffer = buf;
  src.playbackRate.value = 1;
  const f = ctx.createBiquadFilter();
  f.type = type;
  f.frequency.setValueAtTime(freq, t);
  if (sweep) f.frequency.exponentialRampToValueAtTime(Math.max(60, freq * sweep), t + dur);
  f.Q.value = q;
  const g = env(ctx, t, { a: 0.004, d: dur, peak });
  src.connect(f).connect(g);
  src.start(t, Math.random() * 1.2);
  src.stop(t + dur + 0.05);
  return g;
}

function tone(ctx, t, { f0 = 440, f1 = 0, dur = 0.2, type = 'sine', peak = 0.3, detune = 0 }) {
  const o = ctx.createOscillator();
  o.type = type;
  o.detune.value = detune;
  o.frequency.setValueAtTime(f0, t);
  if (f1) o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
  const g = env(ctx, t, { a: 0.006, d: dur, peak });
  o.connect(g);
  o.start(t);
  o.stop(t + dur + 0.05);
  return g;
}

/** 单声部构造：返回接入节点，由调用方连到总线 */
function voice(ctx, name, t, buf) {
  const out = ctx.createGain();
  out.gain.value = 1;
  const add = (node) => node.connect(out);
  switch (name) {
    case 'jump':
      add(noise(ctx, t, { dur: 0.18, freq: 700, q: 0.8, peak: 0.70, sweep: 2.6, buf }));   // 原来 0.25：比落地小 7 倍，起跳听不见
      break;
    case 'land':
      add(tone(ctx, t, { f0: 150, f1: 55, dur: 0.26, peak: 0.5 }));
      add(noise(ctx, t, { dur: 0.2, freq: 420, q: 0.7, type: 'lowpass', peak: 0.35, buf }));
      break;
    case 'step':
      add(noise(ctx, t, { dur: 0.08, freq: 900, q: 1.2, peak: 0.85, buf }));
      break;
    case 'swing':
      add(noise(ctx, t, { dur: 0.2, freq: 600, q: 1.4, peak: 0.5, sweep: 3.2, buf }));
      break;
    case 'hit':
      add(tone(ctx, t, { f0: 190, f1: 70, dur: 0.2, peak: 0.55 }));
      add(noise(ctx, t, { dur: 0.16, freq: 1100, q: 0.9, peak: 0.45, buf }));
      break;
    case 'hurt':
      add(tone(ctx, t, { f0: 210, f1: 120, dur: 0.3, type: 'triangle', peak: 0.4 }));
      add(tone(ctx, t + 0.02, { f0: 233, f1: 130, dur: 0.3, type: 'sawtooth', peak: 0.14 }));   // 微失谐 = 痛感
      add(noise(ctx, t, { dur: 0.22, freq: 500, q: 0.8, type: 'lowpass', peak: 0.3, buf }));
      break;
    case 'die':
      add(tone(ctx, t, { f0: 220, f1: 60, dur: 0.8, type: 'sawtooth', peak: 0.3 }));
      add(noise(ctx, t, { dur: 0.7, freq: 800, q: 0.6, type: 'lowpass', peak: 0.3, sweep: 0.4, buf }));
      break;
    case 'growl':
      add(tone(ctx, t, { f0: 95, f1: 70, dur: 0.5, type: 'sawtooth', peak: 0.3 }));
      add(tone(ctx, t + 0.03, { f0: 140, f1: 90, dur: 0.45, type: 'square', peak: 0.1, detune: 12 }));
      break;
    case 'pickup':
      add(tone(ctx, t, { f0: 880, dur: 0.28, type: 'triangle', peak: 0.3 }));
      add(tone(ctx, t + 0.07, { f0: 1320, dur: 0.32, type: 'triangle', peak: 0.22 }));
      break;
    case 'levelup':
      [523, 659, 784, 1046].forEach((f, i) => add(tone(ctx, t + i * 0.11, { f0: f, dur: 0.36, type: 'triangle', peak: 0.26 })));
      break;
    case 'click':
      add(tone(ctx, t, { f0: 1200, f1: 900, dur: 0.07, type: 'square', peak: 0.24 }));
      break;
    case 'cast_ice':
      add(noise(ctx, t, { dur: 0.6, freq: 2600, q: 0.7, peak: 0.28, sweep: 0.35, buf }));      // 冷气扫过
      [1568, 2093, 2637].forEach((f, i) => add(tone(ctx, t + i * 0.05, { f0: f, dur: 0.5, type: 'triangle', peak: 0.14 })));
      break;
    case 'cast_thunder':
      add(noise(ctx, t, { dur: 0.12, freq: 3000, q: 0.4, type: 'highpass', peak: 0.5, buf }));  // 起手噼啪
      add(tone(ctx, t + 0.02, { f0: 110, f1: 70, dur: 0.55, type: 'sawtooth', peak: 0.22 }));
      add(noise(ctx, t + 0.02, { dur: 0.5, freq: 400, q: 0.5, type: 'bandpass', peak: 0.3, sweep: 2.2, buf }));
      break;
    case 'cast_beam':
      add(tone(ctx, t, { f0: 140, f1: 320, dur: 0.7, type: 'sawtooth', peak: 0.24 }));
      add(noise(ctx, t, { dur: 0.65, freq: 900, q: 2.0, peak: 0.26, sweep: 1.8, buf }));
      break;
    case 'cast_phoenix':
      add(noise(ctx, t, { dur: 0.85, freq: 320, q: 0.6, peak: 0.34, sweep: 6.0, buf }));         // 火焰上扬
      add(tone(ctx, t + 0.05, { f0: 160, f1: 420, dur: 0.7, type: 'triangle', peak: 0.2 }));
      break;
    case 'impact_ice':
      for (let i = 0; i < 5; i++) add(noise(ctx, t + i * 0.035, { dur: 0.1, freq: 2800 + i * 600, q: 2.5, peak: 0.32, buf }));
      add(tone(ctx, t, { f0: 220, f1: 90, dur: 0.3, peak: 0.4 }));
      break;
    case 'impact_thunder':
      add(noise(ctx, t, { dur: 0.18, freq: 2400, q: 0.5, peak: 0.5, buf }));
      add(tone(ctx, t, { f0: 70, f1: 40, dur: 0.8, peak: 0.45 }));                                // 低频轰鸣
      add(noise(ctx, t + 0.02, { dur: 0.7, freq: 260, q: 0.5, type: 'lowpass', peak: 0.4, buf }));
      break;
    case 'impact_beam':
      add(tone(ctx, t, { f0: 300, f1: 80, dur: 0.5, type: 'sawtooth', peak: 0.3 }));
      add(noise(ctx, t, { dur: 0.45, freq: 1200, q: 1.2, peak: 0.35, sweep: 0.4, buf }));
      break;
    case 'impact_phoenix':
      add(noise(ctx, t, { dur: 0.6, freq: 700, q: 0.5, peak: 0.4, sweep: 2.5, buf }));
      add(tone(ctx, t, { f0: 120, f1: 55, dur: 0.6, peak: 0.4 }));
      break;
    default:
      add(noise(ctx, t, { dur: 0.12, freq: 1000, q: 1, peak: 0.2, buf }));
  }
  return out;
}

export function createAudio(opts = {}) {
  const AC = typeof window !== 'undefined' && (window.AudioContext || window.webkitAudioContext);
  let ctx = null, master = null, comp = null, buf = null;
  let muted = !!opts.muted;
  const live = new Map();            // name -> 正在响的个数
  const lastAt = new Map();
  let played = 0, rejected = 0;      // ?audiotest=1 的读数：真正发声的次数 / 被节流挡掉的次数

  function ensure() {
    if (ctx || !AC) return ctx;
    ctx = new AC();
    comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -12;
    comp.knee.value = 12;
    comp.ratio.value = 6;
    comp.attack.value = 0.004;
    comp.release.value = 0.25;
    master = ctx.createGain();
    master.gain.value = muted ? 0 : 0.55;
    master.connect(comp).connect(ctx.destination);
    buf = noiseBuffer(ctx);
    return ctx;
  }

  function canPlay(name, now) {
    const cap = VOICES[name] ?? 6;
    if ((live.get(name) || 0) >= cap) return false;
    const minGap = name === 'step' ? 0.06 : 0.02;
    if (now - (lastAt.get(name) || -9) < minGap) return false;   // 同一帧内不重复叠
    return true;
  }

  /** name 必须出现在 SOUNDS 里；opts: { dist, pan, rate } */
  function play(name, o = {}) {
    if (muted || !SOUNDS[name]) { rejected++; return false; }
    const c = ensure();
    if (!c) { rejected++; return false; }
    if (c.state === 'suspended') c.resume();
    const now = c.currentTime;
    if (!canPlay(name, now)) { rejected++; return false; }
    const meta = SOUNDS[name];
    const t = now + 0.005;
    const v = voice(c, name, t, buf);
    const gain = c.createGain();
    gain.gain.value = meta.gain * attenuation(o.dist ?? 0);
    let tail = v;
    if (o.pan !== undefined && c.createStereoPanner) {
      const p = c.createStereoPanner();
      p.pan.value = Math.max(-1, Math.min(1, o.pan));
      tail.connect(p);
      tail = p;
    }
    tail.connect(gain).connect(master);
    if (o.rate && o.rate !== 1) {
      // 简化：整体音高由 voice 内部决定，外部速率只改总线增益（避免重建整条链）
      gain.gain.value *= Math.min(1, Math.max(0.4, o.rate));
    }
    live.set(name, (live.get(name) || 0) + 1);
    lastAt.set(name, now);
    setTimeout(() => live.set(name, Math.max(0, (live.get(name) || 1) - 1)), meta.dur * 1000 + 80);
    played++;
    return true;
  }

  function setMuted(m) {
    muted = !!m;
    if (master) master.gain.value = muted ? 0 : 0.55;
    return muted;
  }
  function resume() { const c = ensure(); if (c && c.state === 'suspended') c.resume(); return !!c; }
  function getTime() { return ctx ? ctx.currentTime : 0; }

  function stats() {
    let sum = 0;
    for (const v of live.values()) sum += v;
    return { ready: !!ctx, state: ctx ? ctx.state : 'none', played, rejected, live: sum };
  }
  return { play, setMuted, resume, getTime, stats, get muted() { return muted; }, get ready() { return !!ctx; } };
}

/** 离线渲染（浏览器里用 OfflineAudioContext）——给 ?audioprobe=1 出数值证据，node 下用注入的 ctx 工厂 */
export async function renderProbe(makeCtx, name, seconds, sampleRate = 44100) {
  const dur = seconds ?? SOUNDS[name].dur + 0.15;
  const c = makeCtx(2, Math.ceil(dur * sampleRate), sampleRate);
  const master = c.createGain();
  master.gain.value = 0.55 * SOUNDS[name].gain;   // 和 play() 里的总线口径一致（之前漏乘增益，读数偏高）
  master.connect(c.destination);
  const nb = noiseBuffer(c);
  const v = voice(c, name, 0.01, nb);
  v.connect(master);
  const out = await c.startRendering();
  const L = out.getChannelData(0);
  let peak = 0, sum = 0;
  for (let i = 0; i < L.length; i++) { const a = Math.abs(L[i]); if (a > peak) peak = a; sum += L[i] * L[i]; }
  return { name, dur: +dur.toFixed(2), peak: +peak.toFixed(3), rms: +Math.sqrt(sum / L.length).toFixed(4) };
}
