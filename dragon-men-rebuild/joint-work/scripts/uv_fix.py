# -*- coding: utf-8 -*-
"""TASK2 fix: replace the per-vertex nearest-donor UV copy on the added sleeve/socket faces with a
smooth moving-least-squares affine transfer fitted to the local skin UVs (same donor neighbourhood
the builder used). Original geometry (verts/loops) is untouched: only loops whose vertex index is in
a new block are written, and those loops are the tail of the loop array.
Usage: blender -b --factory-startup --python uv_fix.py -- <inblend> <outblend> <keys|all> [report.json]
"""
import bpy, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
import jlib as J

A = sys.argv[sys.argv.index('--') + 1:]
INB, OUTB = A[0], A[1]
KEYS = A[2]
REP = A[3] if len(A) > 3 else None
RIDGE = float(A[4]) if len(A) > 4 else 1e-3
SMOOTH = int(A[5]) if len(A) > 5 else 0
SCRIPT = os.path.dirname(os.path.abspath(__file__))
BR = json.load(open(os.path.join(SCRIPT, '..', 'verify', 'build_report.json'), encoding='utf-8'))

bpy.ops.wm.open_mainfile(filepath=INB)
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = body.matrix_world
N0V = 21870
NV = len(me.vertices)
co = np.array([list(v.co) for v in me.vertices], dtype=np.float64)
W = co @ np.array(MW)[:3, :3].T + np.array(MW)[:3, 3]
polys = [tuple(p.vertices) for p in me.polygons]
pmat = [me.materials[p.material_index].name if me.materials[p.material_index] else '?' for p in me.polygons]
SKIN = J.SKIN
vskin = np.ones(NV, dtype=bool)
for i, p in enumerate(polys):
    if pmat[i] != SKIN:
        for v in p:
            vskin[v] = False
bone_of = {}
gidx = {g.index: g.name for g in body.vertex_groups}
dom = [None] * NV
wmax = np.zeros(NV)
for v in me.vertices:
    for g in v.groups:
        if g.weight > wmax[v.index]:
            wmax[v.index] = g.weight
            dom[v.index] = gidx[g.group]

print('[U] uv layers', [(l.name, l.active_render) for l in me.uv_layers], flush=True)
for m in me.materials:
    if m and m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'UVMAP':
                print('[U] mat %s UVMAP node -> %r' % (m.name, n.uv_map), flush=True)
            if n.type == 'TEX_COORD':
                for o in n.outputs:
                    for lk in o.links:
                        print('[U] mat %s TEX_COORD.%s -> %s.%s' % (m.name, o.name, lk.to_node.name, lk.to_socket.name), flush=True)

LAYERS = [l.name for l in me.uv_layers]
uv = {}
for ln in LAYERS:
    a = np.zeros(len(me.loops) * 2)
    me.uv_layers[ln].data.foreach_get('uv', a)
    uv[ln] = a.reshape(-1, 2)
loop_uv_idx = {}
for ln in LAYERS:
    loop_uv_idx[ln] = None
poly_loop0 = np.array([p.loop_start for p in me.polygons])

newv = np.arange(N0V, NV)


def density(verts, lay):
    """uv-area / 3d-area per face whose vertices all lie in verts"""
    vs = set(int(v) for v in verts)
    u = uv[lay]
    out = []
    for i, p in enumerate(polys):
        if not all(int(v) in vs for v in p):
            continue
        P = W[list(p)]
        a3 = 0.0
        for k in range(1, len(p) - 1):
            a3 += 0.5 * np.linalg.norm(np.cross(P[k] - P[0], P[k + 1] - P[0]))
        if a3 <= 1e-14:
            continue
        T = np.array([u[poly_loop0[i] + k] for k in range(len(p))])
        au = 0.0
        for k in range(1, len(p) - 1):
            au += 0.5 * abs((T[k][0] - T[0][0]) * (T[k + 1][1] - T[0][1]) - (T[k + 1][0] - T[0][0]) * (T[k][1] - T[0][1]))
        out.append(au / a3)
    return np.array(out)


TARGET = 'all' if KEYS == 'all' else set(KEYS.split(','))
rep = {}
for jd in BR['joints']:
    key, base, nvp, med = jd['key'], int(jd['base']), int(jd['nvp']), float(jd['med'])
    if TARGET != 'all' and key not in TARGET:
        continue
    cb, par = jd['bone'], jd['par']
    Jw = np.array(jd['J'], dtype=np.float64)
    blk = np.arange(base, base + nvp)
    R = max(0.06, 1.5 * med)
    roots = (cb, par)

    def okbone(i):
        d = dom[i]
        if d is None:
            return False
        return d in roots or any(d.startswith(r.rsplit(':', 1)[-1]) or r.endswith(d.rsplit(':', 1)[-1]) for r in roots)

    cand = []
    for rr in (R, 2 * R, 4 * R, 8 * R):
        cand = [i for i in range(N0V) if vskin[i] and okbone(i) and np.linalg.norm(W[i] - Jw) < rr]
        if len(cand) >= 8:
            break
    if len(cand) < 8:
        dd = np.linalg.norm(W[:N0V] - Jw, axis=1)
        cand = [int(i) for i in np.argsort(dd)[:32] if vskin[i]]
    C = np.array(cand, dtype=np.int64)
    D = W[C] - Jw
    before = {}
    after = {}
    for ln in LAYERS:
        if ln != 'map1':
            continue
        before[ln] = density(blk, ln)
        U = uv[ln]
        pd = np.zeros((NV, 2))  # donor uv per vertex (first loop wins, same as builder)
        seen = np.zeros(NV, dtype=bool)
        for li, lp in enumerate(me.loops):
            vi = lp.vertex_index
            if not seen[vi]:
                pd[vi] = U[li]
                seen[vi] = True
        DU = pd[C]
        newuv = {}
        for vi in blk:
            d = np.linalg.norm(D - (W[vi] - Jw), axis=1)
            k = np.argsort(d)[:40]
            dk = d[k]
            sig = max(1e-4, med)
            wgt = np.exp(-(dk / sig) ** 2) + 1e-6
            X = np.hstack([np.ones((len(k), 1)), D[k]])
            y = DU[k]
            def fit(wg):
                Xw = X * wg[:, None]
                A = Xw.T @ X
                lam = RIDGE * np.trace(A) / A.shape[0]
                A = A + np.eye(A.shape[0]) * lam
                sol, *_ = np.linalg.lstsq(A, Xw.T @ y, rcond=None)
                return sol
            sol = fit(wgt)
            res = np.linalg.norm(y - X @ sol, axis=1)
            keep = res <= max(2.5 * np.median(res), 1e-6)
            if keep.sum() >= 6:
                sol = fit(wgt * keep)
            newuv[vi] = sol[0] + sol[1:].T @ (W[vi] - Jw)
        if SMOOTH > 0:
            blkset = set(int(v) for v in blk)
            nb = {}
            for e in me.edges:
                a0, b0 = int(e.vertices[0]), int(e.vertices[1])
                nb.setdefault(a0, set()).add(b0)
                nb.setdefault(b0, set()).add(a0)
            adj = {v: (nb.get(v, set()) & blkset) for v in blkset}
            pinned = set(v for v in blkset if (nb.get(v, set()) - blkset))
            for _ in range(SMOOTH):
                cur = dict(newuv)
                for v in blkset:
                    if v in pinned or not adj[v]:
                        continue
                    newuv[v] = 0.5 * cur[v] + 0.5 * np.mean([cur[n] for n in adj[v]], axis=0)
            print('[U] %-11s smoothed %d iters, pinned %d of %d verts' % (key, SMOOTH, len(pinned), len(blkset)), flush=True)
        for li, lp in enumerate(me.loops):
            vi = lp.vertex_index
            if vi in newuv:
                me.uv_layers[ln].data[li].uv = Vector((float(newuv[vi][0]), float(newuv[vi][1])))
        # refresh array for density measure
        a = np.zeros(len(me.loops) * 2)
        me.uv_layers[ln].data.foreach_get('uv', a)
        uv[ln] = a.reshape(-1, 2)
        after[ln] = density(blk, ln)
        if ln == 'map1':
            don = density(np.array(C, dtype=np.int64), ln)
            donm = float(np.median(don)) if len(don) else 0.0
            meda = float(np.median(after[ln])) if len(after[ln]) else 0.0
            if donm > 0 and meda > 0 and (donm / meda < 0.8 or donm / meda > 1.25):
                k = math.sqrt(donm / meda)
                cen = np.mean([newuv[v] for v in blk], axis=0)
                for li, lp in enumerate(me.loops):
                    vi = lp.vertex_index
                    if vi in newuv:
                        q = cen + k * (newuv[vi] - cen)
                        me.uv_layers[ln].data[li].uv = Vector((float(q[0]), float(q[1])))
                b = np.zeros(len(me.loops) * 2)
                me.uv_layers[ln].data.foreach_get('uv', b)
                uv[ln] = b.reshape(-1, 2)
                after[ln] = density(blk, ln)
                print('[U]   density match k=%.3f donor_med %.3f -> block med %.3f' % (k, donm, float(np.median(after[ln]))), flush=True)
    if 'map1' in before:
        b, a = before['map1'], after['map1']
        rep[key] = dict(faces=int(len(b)), med_before=float(np.median(b)), med_after=float(np.median(a)),
                        zero_before=int((b < 1e-9).sum()), zero_after=int((a < 1e-9).sum()),
                        smear_before=int((b > 3 * max(np.median(b), 1e-12)).sum()),
                        smear_after=int((a > 3 * max(np.median(a), 1e-12)).sum()),
                        max_before=float(b.max()), max_after=float(a.max()))
        r = rep[key]
        print('[U] %-11s faces %4d uvdens med %.2f->%.2f  zero %d->%d  smear %d->%d  max %.0f->%.0f'
              % (key, r['faces'], r['med_before'], r['med_after'], r['zero_before'], r['zero_after'],
                 r['smear_before'], r['smear_after'], r['max_before'], r['max_after']), flush=True)

bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[U] saved', OUTB, os.path.getsize(OUTB), flush=True)
if REP:
    json.dump(rep, open(REP, 'w', encoding='utf-8'), indent=1)
print('[U] DONE', flush=True)
