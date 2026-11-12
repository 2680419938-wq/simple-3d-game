# -*- coding: utf-8 -*-
"""Acceptance check for dragon-men-game-walk: AC1-AC9 measured on the exported GLBs."""
import hashlib, json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib
from _glbpose import min_pair_dist

OUT = sys.argv[1] if len(sys.argv) > 1 else r'D:\ai\建模\dragon-men-game-walk'
REF = r'D:\ai\建模\dragon-men-game\DragonMan_Game.glb'
FILES = ['DragonMan_Game.glb', 'DragonMan_TPose.glb', 'DragonMan_Game_LOD1.glb', 'DragonMan_Game_LOD2.glb']
FAIL = []

def bad(tag, msg):
    FAIL.append(tag + ': ' + msg)

def hd(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

# ---------- AC9: four-file structure ----------
print('=== AC9 structure ===')
ms = {}
for f in FILES:
    p = os.path.join(OUT, f); m = glblib.Model(p); ms[f] = m
    print('%-26s %9d B  sha256 %s  tris %6d  joints %d  anims %s'
          % (f, os.path.getsize(p), hd(p), m.tris, len(m.joints), sorted(m.anims)))
base = ms[FILES[0]]
exp_tris = {FILES[0]: 52200, FILES[2]: 26501, FILES[3]: 11644}
for f, m in ms.items():
    if m.jnames != base.jnames: bad('AC9', f + ' joint names/order differ')
    if any('armor' in (n.get('name') or '').lower() for n in m.nodes): bad('AC9', f + ' armor node')
    if f in exp_tris and m.tris != exp_tris[f]: bad('AC9', f + ' tris %d != %d' % (m.tris, exp_tris[f]))
    if f != FILES[1] and sorted(m.anims) != ['Idle_Lively', 'Walk']: bad('AC9', f + ' anims ' + str(sorted(m.anims)))
print('joint order: %d names, identical across all four: %s'
      % (len(base.jnames), all(m.jnames == base.jnames for m in ms.values())))

# rest skeleton TRS + pivot + sole
print('rest skeleton / pivot / sole:')
for f, m in ms.items():
    W = m.world(None, 0.0)
    jt = {n: W[m.joints[i]][:3, 3] for i, n in enumerate(m.jnames)}
    V = m.skin_verts(None, 0.0)
    ank = 0.5 * (jt['foot.L'] + jt['foot.R'])
    print('  %-26s ankleMid xz (%+.3e,%+.3e)  soleMinY %+.3e  pelvisY %.6f'
          % (f, ank[0], ank[2], V[:, 1].min(), jt['pelvis'][1]))
    if abs(ank[0]) > 1e-6 or abs(ank[2]) > 1e-6: bad('AC9', f + ' pivot %.2e' % max(abs(ank[0]), abs(ank[2])))
    if f == FILES[0] and abs(V[:, 1].min()) > 1e-6: bad('AC9', f + ' sole y %.2e' % V[:, 1].min())
ref_trs = None
for f, m in ms.items():
    W = m.world(None, 0.0)
    cur = np.stack([W[m.joints[i]] for i, n in enumerate(m.jnames)])
    if ref_trs is None: ref_trs = cur
    else:
        d = float(np.abs(cur - ref_trs).max())
        print('  %-26s max rest-TRS delta vs LOD0 %.2e' % (f, d))
        if d > 1e-6: bad('AC9', f + ' skeleton TRS drift %.2e' % d)

# ---------- AC8: Idle identical to the shipped game package ----------
print('=== AC8 Idle channels vs dragon-men-game ===')
mr = glblib.Model(REF)
print('reference anims:', sorted(mr.anims))
d8 = 0.0; n8 = 0
for name in ('Idle_Lively',):
    ref = mr.anims[name]
    for node, paths in ms[FILES[0]].anims[name].items():
        if node not in ref: continue
        for p, (t, v, it) in paths.items():
            if p not in ref[node]: continue
            t0, v0, _ = ref[node][p]
            if len(t) != len(t0) or np.abs(t - t0).max() > 1e-6: bad('AC8', '%s %s times' % (name, p)); continue
            d8 = max(d8, float(np.abs(v - v0).max())); n8 += 1
print('AC8 Idle_Lively: %d channels compared, max |delta| vs shipped game GLB %.3e (limit 1e-6)' % (n8, d8))
if d8 > 1e-6: bad('AC8', 'idle delta %.3e' % d8)
if 'Walk' in mr.anims:
    dw = 0.0
    for node, paths in ms[FILES[0]].anims['Walk'].items():
        for p, (t, v, it) in paths.items():
            if node in mr.anims['Walk'] and p in mr.anims['Walk'][node]:
                t0, v0, _ = mr.anims['Walk'][node][p]
                if len(t0) == len(t):
                    dw = max(dw, float(np.abs(v - v0).max()))
    print('   (Walk vs old Walk, informational: max |delta| %.4f - must differ)' % dw)

# ---------- seam reference points (same metric, same asset family) ----------
print('=== AC1 seam reference: same metric on the accepted rest pose and shipped Idle ===')
for tag, fp, act, tt in [('TPose (rest, no anim)', 'DragonMan_TPose.glb', None, 0.0),
                         ('Game Idle_Lively f1 ', 'DragonMan_Game.glb', 'Idle_Lively', 0.0)]:
    mm = glblib.Model(os.path.join(OUT, fp))
    jj = {n: mm.joints[i] for i, n in enumerate(mm.jnames)}
    dn = mm.dominant_joint_names()
    chx = mm.anims[act] if act else None
    Wp = mm.world(chx, tt) if chx else mm.world(None, 0.0)
    Vp = mm.skin_verts(chx, tt) if chx else mm.skin_verts(None, 0.0)
    aa = [np.where(dn == 'thigh.' + s)[0] for s in 'LR']
    bb = [np.where(np.isin(dn, ['shin.' + s, 'foot.' + s, 'toe.01.' + s, 'toe.02.' + s, 'toe.03.' + s]))[0]
          for s in 'LR']
    d = []
    for k in range(2):
        vi = np.array([int(x) for x in aa[k]]); wi = np.array([int(x) for x in bb[k]])
        A, B = Vp[vi], Vp[wi]
        best = 1e9
        for i0 in range(0, len(A), 400):
            blk = A[i0:i0 + 400]
            dd = ((blk[:, None, :] - B[None, :, :]) ** 2).sum(-1).min()
            best = min(best, float(dd))
        d.append(np.sqrt(best))
    print('%s  L %.4f  R %.4f' % (tag, d[0], d[1]))

# ---------- AC1-AC7 on the Walk action of LOD0 ----------
print('=== AC1-AC7 Walk (LOD0, exported action sampled at 30 fps) ===')
m = base
ch = m.anims['Walk']
tref = ch[m.joints[m.jnames.index('pelvis')]]['rotation'][0]
print('Walk keys %d  t %.4f..%.4f s  step %.5f' % (len(tref), tref[0], tref[-1], tref[1] - tref[0]))
SA = [np.where(m.dominant_joint_names() == 'thigh.' + s)[0] for s in 'LR']
SB = [np.where(np.isin(m.dominant_joint_names(),
                       ['shin.' + s, 'foot.' + s, 'toe.01.' + s, 'toe.02.' + s, 'toe.03.' + s]))[0] for s in 'LR']
JI = {n: m.joints[i] for i, n in enumerate(m.jnames)}
Y = np.array([0., 1., 0.])
NF = 33
rows = []
for f in range(NF):
    t = f / 30.0
    W = m.world(ch, t); V = m.skin_verts(ch, t)
    r = dict(f=f + 1, pel=float(W[JI['pelvis']][1, 3]), minz=float(V[:, 1].min()), seam={}, knee={},
             fy={}, fz={})
    for k, s in enumerate('LR'):
        d, _ = min_pair_dist(V[SA[k]], V[SB[k]])
        r['seam'][s] = d
        a = W[JI['thigh.' + s]][:3, :3] @ Y; b = W[JI['shin.' + s]][:3, :3] @ Y
        r['knee'][s] = math.degrees(math.acos(max(-1., min(1., float(np.dot(a / np.linalg.norm(a), b / np.linalg.norm(b)))))))
        r['fy'][s] = float(W[JI['foot.' + s]][1, 3]); r['fz'][s] = float(W[JI['foot.' + s]][2, 3])
    rows.append(r)
    print('f%02d pel %.4f seamL %.4f seamR %.4f kneeL %5.2f kneeR %5.2f minz %+.4f'
          % (r['f'], r['pel'], r['seam']['L'], r['seam']['R'], r['knee']['L'], r['knee']['R'], r['minz']))
BASEY = {s: min(x['fy'][s] for x in rows) for s in 'LR'}
for r in rows:
    print('f%02d clrL %.4f clrR %.4f  (foot height above its own lowest frame)'
          % (r['f'], r['fy']['L'] - BASEY['L'], r['fy']['R'] - BASEY['R']))

# AC1
worst = {s: max(x['seam'][s] for x in rows) for s in 'LR'}
print('AC1 shell seam (thigh <-> shin/foot/toe): L max %.4f  R max %.4f  (limit 0.0200)' % (worst['L'], worst['R']))
if worst['L'] > 0.020: bad('AC1', 'L seam %.4f' % worst['L'])
if worst['R'] > 0.020: bad('AC1', 'R seam %.4f' % worst['R'])
# AC2
kpk = {s: max(x['knee'][s] for x in rows) for s in 'LR'}
print('AC2 knee peak: L %.2f  R %.2f  (limit 25.00)' % (kpk['L'], kpk['R']))
for s in 'LR':
    if kpk[s] > 25.0: bad('AC2', '%s %.2f' % (s, kpk[s]))
# AC3
pl = [x['pel'] for x in rows]
print('AC3 pelvis: %.4f..%.4f (window 0.5900..0.6100)' % (min(pl), max(pl)))
if min(pl) < 0.590 or max(pl) > 0.610: bad('AC3', 'pelvis %.4f..%.4f' % (min(pl), max(pl)))
# AC4/AC5
print('AC4/AC5 stance travel + swing clearance (foot joint; stance = planted within 0.5 mm of its own min AND moving backward; circular over the 32 distinct frames):')
ND = NF - 1   # f33 duplicates f1 bit-exactly -> 32 distinct frames per cycle
def dnxt(i): return (i + 1) % ND
for s in 'LR':
    fy = [x['fy'][s] for x in rows][:ND]; fz = [x['fz'][s] for x in rows][:ND]
    bY = min(fy)
    planted = [(abs(fy[i] - bY) < 5e-4) and (fz[dnxt(i)] - fz[i] < 0.0) for i in range(ND)]
    runs = []
    for start in range(ND):
        if not planted[start]: continue
        run = []
        for k in range(ND):
            i = (start + k) % ND
            if not planted[i]: break
            run.append(i)
        runs.append(run)
    run = max(runs, key=len)
    steps = [fz[dnxt(run[i])] - fz[run[i]] for i in range(len(run) - 1)]
    mean = float(np.mean(steps))
    trav = -float(np.sum(steps)); dev = max(abs(d - mean) for d in steps) / abs(mean)
    clr = max(fy) - min(fy)
    print('  %s stance f%d..f%d (%d frames, %d steps) travel %.4f m step %.5f dev %.2f%%  clearance %.4f m'
          % (s, run[0] + 1, run[-1] + 1, len(run), len(steps), trav, mean, 100 * dev, clr))
    if len(steps) < 5: bad('AC4', s + ' stance run too short')
    if not (0.08 <= trav <= 0.13): bad('AC4', s + ' travel %.4f' % trav)
    if dev > 0.15: bad('AC4', s + ' step dev %.1f%%' % (100 * dev))
    if not (0.012 <= clr <= 0.025): bad('AC5', s + ' clearance %.4f' % clr)
# AC6
mz = min(x['minz'] for x in rows)
print('AC6 lowest vertex over 33 frames: %+.4f m (limit -0.0020)' % mz)
if mz < -0.002: bad('AC6', 'minz %.4f' % mz)
# AC7
ts = ch[list(ch)[0]]['rotation'][0]
K0, K1 = float(ts[0]), float(ts[-1])
W0 = m.world(ch, 0.0); W1 = m.world(ch, 32 / 30.0)
d7 = max(float(np.abs(W0[i] - W1[i]).max()) for i in W0)
Wk0 = m.world(ch, K0); Wk1 = m.world(ch, K1)
d7k = max(float(np.abs(Wk0[i] - Wk1[i]).max()) for i in Wk0)
print('AC7 world-matrix delta: %.3e at t=0 vs 32/30 (nominal) | %.3e at the stored key times t=%.6f vs %.6f (exact)' % (d7, d7k, K0, K1))
if d7k > 0:
    print('  keys differ by %.3e' % d7k)
if d7k > 1e-9: bad('AC7', 'loop delta %.3e' % d7k)
print('implied ground speed 2*travel/1.0667s = %.4f m/s' % (2 * 0.1111 / (32 / 30.0)))
print('')
print('RESULT', 'ALL PASS' if not FAIL else 'FAIL: ' + '; '.join(FAIL))
