# -*- coding: utf-8 -*-
"""TASK A build v2: mask-driven recessed skin lining inside the hip crease.
Measures the rest-pose see-through void (bg rays within 0.052 m of the joint), centres a closed lens shell on
the void, recesses it behind the crease mouth, sweeps lens radius/recess until the rest-frame change lands in
[0.40%,0.60%] with no pixels stolen from skin, then appends it to DragonMan_Body (Skin material, linear
thigh/pelvis weights, MLS affine UVs on map1 for the new loops only).
Usage: blender -b --factory-startup --python v2_bowl.py -- <inblend> <outblend> <camjson> <report.json>
"""
import bpy, bmesh, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import jlib as JL

A = sys.argv[sys.argv.index('--') + 1:]
INB, OUTB, CAMJSON, REP = A[0], A[1], A[2], A[3]
N = 320
cams = json.load(open(CAMJSON, encoding='utf-8'))
BR = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'verify', 'build_report.json'), encoding='utf-8'))
JD = {j['key']: j for j in BR['joints']}
WTMAX = 0.30
FLAT = 0.62
KEYS = ('R_hip', 'L_hip')

bpy.ops.wm.open_mainfile(filepath=INB)
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data.action = None
JL.clear_pose(arm)
bpy.context.view_layer.update()
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
co0 = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co0)
co0 = co0.copy().reshape(-1, 3)
W = co0 @ MW[:3, :3].T + MW[:3, 3]
N0V = len(me.vertices); N0P = len(me.polygons)
polys = [tuple(p.vertices) for p in me.polygons]
pmat = [(me.materials[p.material_index].name if me.materials[p.material_index] else '?') for p in me.polygons]
skin_i = [m.name for m in me.materials].index(JL.SKIN)
gname = {g.index: g.name for g in body.vertex_groups}
vski = np.ones(N0V, dtype=bool)
for i, p in enumerate(polys):
    if pmat[i] != JL.SKIN:
        for v in p:
            vski[v] = False
dom = [None] * N0V
for v in me.vertices:
    best = 0.0
    for g in v.groups:
        if g.weight > best:
            best = g.weight; dom[v.index] = gname[g.group]
alltris = []
for p in polys:
    for k in range(1, len(p) - 1):
        alltris.append((p[0], p[k], p[k + 1]))
LAY = 'map1'
uva = np.zeros(len(me.loops) * 2)
me.uv_layers[LAY].data.foreach_get('uv', uva)
UVL = uva.reshape(-1, 2)
pd = np.zeros((N0V, 2)); seen = np.zeros(N0V, dtype=bool)
for li, lp in enumerate(me.loops):
    vi = lp.vertex_index
    if vi < N0V and not seen[vi]:
        pd[vi] = UVL[li]; seen[vi] = True
print('[L] %d verts %d polys  skin verts %d  map1 loops %d' % (N0V, N0P, int(vski.sum()), len(me.loops)), flush=True)


def frame(key):
    c = cams[key]
    J = np.array(c['J'], dtype=np.float64)
    dv = Vector(c['front']).normalized()
    cloc = Vector(J) + dv * 6.0
    q = (Vector(J) - cloc).normalized().to_track_quat('-Z', 'Y')
    M4 = q.to_matrix()
    rgt = np.array(M4.col[0], dtype=np.float64); upp = np.array(M4.col[1], dtype=np.float64)
    fwd = -np.array(M4.col[2], dtype=np.float64)
    return J, np.array(cloc, dtype=np.float64), rgt, upp, fwd, float(c['scale_front'])


def pxdir(px, py, cloc, rgt, upp, sca):
    return cloc + rgt * (((px + 0.5) / N - 0.5) * sca) + upp * (((py + 0.5) / N - 0.5) * sca)


def void_scan(Vbody, cloc, rgt, upp, fwd, sca, J, rad=0.052):
    bB = BVHTree.FromPolygons([tuple(x) for x in Vbody], alltris, all_triangles=True)
    V = np.zeros((N, N), bool); DEP = np.full((N, N), -1.0)
    for py in range(N):
        for px in range(N):
            o = pxdir(px, py, cloc, rgt, upp, sca)
            h = bB.ray_cast(Vector(o), Vector(fwd), 12.0)
            if h[0] is None:
                s = float(fwd @ (J - o))
                if float(np.linalg.norm(o + s * fwd - J)) < rad:
                    V[py, px] = True
            else:
                DEP[py, px] = float((np.array(h[0]) - o) @ fwd)
    return V, DEP


def ell(r, cen, outn, e1, e2, nseg=26, nring=9):
    V = []
    for i in range(nring + 1):
        th = math.pi * i / (nring + 1)
        for k in range(nseg):
            ph = 2.0 * math.pi * k / nseg
            V.append((math.cos(th) * FLAT * r, math.sin(th) * math.cos(ph) * r, math.sin(th) * math.sin(ph) * r))
    V.append((FLAT * r, 0.0, 0.0)); V.append((-FLAT * r, 0.0, 0.0))
    F = []
    for i in range(nring):
        for k in range(nseg):
            k2 = (k + 1) % nseg
            b0 = i * nseg; b1 = (i + 1) * nseg
            F.append((b0 + k, b0 + k2, b1 + k2, b1 + k))
    fp = len(V) - 2; bp = len(V) - 1
    for k in range(nseg):
        k2 = (k + 1) % nseg
        F.append((bp, k, k2))
        F.append((fp, (nring * nseg) + k2, (nring * nseg) + k))
    V = np.array(V)
    P = V[:, 0:1] * outn[None, :] + V[:, 1:2] * e1[None, :] + V[:, 2:3] * e2[None, :] + cen[None, :]
    return P, F


def measure(Vbody, Vfun, Ffun, cloc, rgt, upp, fwd, sca):
    tF = []
    for f in Ffun:
        for k in range(1, len(f) - 1):
            tF.append((f[0], f[k], f[k + 1]))
    bB = BVHTree.FromPolygons([tuple(x) for x in Vbody], alltris, all_triangles=True)
    bF = BVHTree.FromPolygons([tuple(x) for x in Vfun], tF, all_triangles=True)
    rel = Vfun - cloc
    a = rel @ rgt; b = rel @ upp
    px0 = int(max(0, math.floor((a.min() / sca + 0.5) * N) - 2)); px1 = int(min(N, math.ceil((a.max() / sca + 0.5) * N) + 2))
    py0 = int(max(0, math.floor((b.min() / sca + 0.5) * N) - 2)); py1 = int(min(N, math.ceil((b.max() / sca + 0.5) * N) + 2))
    op = steal = vis = 0
    for py in range(py0, py1):
        for px in range(px0, px1):
            o = pxdir(px, py, cloc, rgt, upp, sca)
            hf = bF.ray_cast(Vector(o), Vector(fwd), 12.0)
            if hf[0] is None:
                continue
            vis += 1
            hb = bB.ray_cast(Vector(o), Vector(fwd), 12.0)
            df = float((np.array(hf[0]) - o) @ fwd)
            if hb[0] is None:
                op += 1
            elif df < float((np.array(hb[0]) - o) @ fwd) - 1e-4:
                steal += 1
    return op, vis, steal


def mls_uv(P, J, med, roots):
    cand = [i for i in range(N0V) if vski[i] and dom[i] in roots and np.linalg.norm(W[i] - J) < max(0.10, 3.0 * med)]
    if len(cand) < 8:
        dd = np.linalg.norm(W[:N0V] - J, axis=1)
        cand = [int(i) for i in np.argsort(dd)[:40] if vski[i]]
    C = np.array(cand, dtype=np.int64)
    D = W[C] - J; DU = pd[C]
    sig = max(1e-3, med)
    out = np.zeros((len(P), 2))
    for i, p in enumerate(P):
        d = np.linalg.norm(D - (p - J), axis=1)
        k = np.argsort(d)[:40]
        dk = d[k]
        wgt = np.exp(-(dk / sig) ** 2) + 1e-6
        X = np.hstack([np.ones((len(k), 1)), D[k]])
        y = DU[k]

        def fit(wg):
            Xw = X * wg[:, None]
            sol, *_ = np.linalg.lstsq(Xw.T @ X, Xw.T @ y, rcond=None)
            return sol
        sol = fit(wgt)
        res = np.linalg.norm(y - X @ sol, axis=1)
        keep = res <= max(2.5 * np.median(res), 1e-6)
        if keep.sum() >= 6:
            sol = fit(wgt * keep)
        out[i] = sol[0] + sol[1:].T @ (p - J)
    return out, len(cand)


report = {'wtmax': WTMAX, 'flat': FLAT, 'hips': {}}
for KEY in KEYS:
    c = cams[KEY]; jd = JD[KEY]
    CHILD, PAR = jd['bone'], jd['par']
    med = float(jd['med'])
    J, cloc, rgt, upp, fwd, sca = frame(KEY)
    outn = -fwd
    bn = arm.data.bones[CHILD]; hb = np.array(arm.matrix_world @ bn.head_local); tb = np.array(arm.matrix_world @ bn.tail_local)
    pn = arm.data.bones[PAR]; phb = np.array(arm.matrix_world @ pn.head_local); ptb = np.array(arm.matrix_world @ pn.tail_local)

    def segd(Pp, a, b):
        ab = b - a; L2 = float(ab @ ab)
        t = np.clip(((Pp - a) @ ab) / max(L2, 1e-12), 0.0, 1.0)
        return np.linalg.norm(Pp - (a + t[:, None] * ab), axis=1)

    JL.clear_pose(arm)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    obe = body.evaluated_get(dg)
    m2 = obe.to_mesh()
    Vb0 = np.empty(len(m2.vertices) * 3); m2.vertices.foreach_get('co', Vb0)
    Vb0 = Vb0.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
    obe.to_mesh_clear()
    VOID, DEP = void_scan(Vb0, cloc, rgt, upp, fwd, sca, J)
    nv = int(VOID.sum())
    ys, xs = np.nonzero(VOID)
    mx, my = float(xs.mean()), float(ys.mean())
    area_px = nv
    rpx = math.sqrt(area_px / math.pi)
    dm = DEP[DEP > 0]
    dep_med = float(np.median(dm)) if len(dm) else 11.9
    print('[L] %s void %d px  centroid (%.1f,%.1f)  equiv radius %.1f px = %.4f m  rim depth med %.4f' %
          (KEY, nv, mx, my, rpx, rpx * sca / N, dep_med), flush=True)
    cen_px = pxdir(int(round(mx)), int(round(my)), cloc, rgt, upp, sca)
    dirn = np.array(fwd, dtype=np.float64)
    rpx_m = rpx * sca / N
    best = None
    for rf in (0.55, 0.75, 0.95):
        r = rf * rpx_m
        for recess in (0.010, 0.020):
            cen = cen_px + dirn * (dep_med + recess)
            P, F = ell(r, cen, outn, rgt, upp)
            dth = segd(P, hb, tb); dpa = segd(P, phb, ptb)
            wt = np.minimum(dpa / np.maximum(dpa + dth, 1e-9), WTMAX)
            op, vis, steal = measure(Vb0, P, F, cloc, rgt, upp, fwd, sca)
            fr = 100.0 * op / (N * N)
            ok = (0.40 <= fr <= 0.60) and steal <= 5
            print('[L] %s rf %.2f r %.4f recess %.3f -> rest %d (%.3f%%) vis %d steal %d %s' %
                  (KEY, rf, r, recess, op, fr, vis, steal, 'OK' if ok else ''), flush=True)
            row = dict(rf=rf, r=round(r, 5), recess=recess, rest_opened=int(op), rest_frac=round(fr, 4),
                       vis=int(vis), steal=int(steal), ok=ok)
            if best is None or (ok and not best['ok']) or (ok == best['ok'] and abs(fr - 0.50) < abs(best['rest_frac'] - 0.50)):
                best = row
    print('[L] %s chosen rf %.2f r %.4f recess %.3f rest %.3f%% steal %d' % (KEY, best['rf'], best['r'], best['recess'], best['rest_frac'], best['steal']), flush=True)
    cen = cen_px + dirn * (dep_med + best['recess'])
    P, F = ell(best['r'], cen, outn, rgt, upp)
    dth = segd(P, hb, tb); dpa = segd(P, phb, ptb)
    wt = np.minimum(dpa / np.maximum(dpa + dth, 1e-9), WTMAX)
    uvn, ndon = mls_uv(P, J, med, (CHILD, PAR))
    bm = bmesh.new(); bm.from_mesh(me)
    uvl = bm.loops.layers.uv[LAY]
    nv0 = len(bm.verts)
    bv = [bm.verts.new(Vector((float(p[0]), float(p[1]), float(p[2])))) for p in P]
    bm.verts.index_update()
    nfaces = 0
    for f in F:
        try:
            face = bm.faces.new([bv[i] for i in f])
        except ValueError:
            continue
        face.material_index = skin_i
        face.smooth = True
        for lp, vi in zip(face.loops, f):
            lp[uvl].uv = (float(uvn[vi][0]), float(uvn[vi][1]))
        nfaces += 1
    bm.to_mesh(me); bm.free(); me.update()
    for i in range(len(P)):
        for nm, ww in ((CHILD, wt[i]), (PAR, 1.0 - wt[i])):
            body.vertex_groups[nm].add([nv0 + i], float(ww), 'REPLACE')
    co1 = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co1)
    co1 = co1.reshape(-1, 3)
    dmax = float(np.abs(co1[:N0V] - co0).max())
    print('[L] %s appended %d verts %d faces (mesh %d/%d loops %d) donors %d orig max|d| %.3e' %
          (KEY, len(P), nfaces, len(me.vertices), len(me.polygons), len(me.loops), ndon, dmax), flush=True)
    report['hips'][KEY] = {'rf': best['rf'], 'r': best['r'], 'recess': best['recess'], 'nv': int(len(P)), 'nf': int(nfaces),
                           'base_v': int(nv0), 'rest_frac': best['rest_frac'], 'steal': best['steal'], 'void_px': nv,
                           'void_centroid_px': [round(mx, 2), round(my, 2)], 'rim_depth_med': round(dep_med, 5),
                           'wt_min': float(wt.min()), 'wt_max': float(wt.max()), 'orig_dmax': dmax}
json.dump(report, open(REP, 'w'), indent=1)
JL.clear_pose(arm)
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[L] SAVED', OUTB, os.path.getsize(OUTB), flush=True)
