# -*- coding: utf-8 -*-
"""TASK A: recessed skin funnel lining INSIDE the thigh root (a socket cavity), appended to DragonMan_Body.
Sweeps (mouth radius, depth, taper, mouth offset) by measuring the hip_gapcheck counterfactual coverage
on a skinned proxy, then builds the best candidate with blended thigh/pelvis weights and MLS UVs.
Usage: blender -b --factory-startup --python v2_socket.py -- <inblend> <outblend> <camjson> <outjson> [KEY] [mode]
"""
import bpy, bmesh, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import jlib as JL

A = sys.argv[sys.argv.index('--') + 1:]
INB, OUTB, CAMJSON, OUTJ = A[0], A[1], A[2], A[3]
KEY = A[4] if len(A) > 4 else 'R_hip'
MODE = A[5] if len(A) > 5 else 'full'
N = 320
SKIN = JL.SKIN
SOCKMIN = 22814
cams = json.load(open(CAMJSON, encoding='utf-8'))
c = cams[KEY]
J = np.array(c['J'], dtype=np.float64)
BR = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'verify', 'build_report.json'), encoding='utf-8'))
JD = [j for j in BR['joints'] if j['key'] == KEY][0]
MED = float(JD['med']); CHILD, PAR = JD['bone'], JD['par']

bpy.ops.wm.open_mainfile(filepath=INB)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
ACT = arm.animation_data.action if arm.animation_data else None
if ACT is not None:
    arm.animation_data.action = None
JL.clear_pose(arm)
bpy.context.view_layer.update()
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
MWi = Matrix(body.matrix_world).inverted()
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
W = co.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
N0V = len(me.vertices); N0P = len(me.polygons)
polys = [tuple(p.vertices) for p in me.polygons]
pmat = [(me.materials[p.material_index].name if me.materials[p.material_index] else '?') for p in me.polygons]
skin_i = [m.name for m in me.materials].index(SKIN)
gidx = {g.index: g.name for g in body.vertex_groups}
vgr = [dict((gidx[g.group], g.weight) for g in v.groups) for v in me.vertices]
have = set(gidx.values())
trisA, ownA, trisS, ownS = [], [], [], []
for i, p in enumerate(polys):
    for k in range(1, len(p) - 1):
        trisA.append((p[0], p[k], p[k + 1])); ownA.append(i)
    if pmat[i] == SKIN and min(p) < N0V:
        for k in range(1, len(p) - 1):
            trisS.append((p[0], p[k], p[k + 1])); ownS.append(i)
vA = [tuple(x) for x in W]
bvhAll = BVHTree.FromPolygons(vA, trisA, all_triangles=True)
bvhSkin = BVHTree.FromPolygons(vA, trisS, all_triangles=True)
print('[S] verts %d polys %d skin_i %d tris all %d skin %d' % (N0V, N0P, skin_i, len(trisA), len(trisS)), flush=True)

# ---- thigh axis from rest bones ----
bn = arm.data.bones[CHILD]
hb = arm.matrix_world @ bn.head_local
tb = arm.matrix_world @ bn.tail_local
AX = np.array(tb - hb, dtype=np.float64)
AX = AX / np.linalg.norm(AX)
print('[S] thigh head %s axis %s len %.4f' % ([round(float(x), 4) for x in hb], [round(float(x), 4) for x in AX], float((tb - hb).length)), flush=True)
JV = np.array(hb, dtype=np.float64)


def basis(a):
    t = np.array([0.0, 0.0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u1 = np.cross(a, t); u1 /= np.linalg.norm(u1)
    u2 = np.cross(a, u1)
    return u1, u2


E1, E2 = basis(AX)


def funnel(rm, t0, tmax, taper, nseg=24, inside=0.0025):
    st = [t0, t0 + 0.10 * tmax, t0 + 0.30 * tmax, t0 + 0.55 * tmax, t0 + 0.80 * tmax, t0 + 1.00 * tmax]
    fr = [1.0, 0.94, 0.74, 0.52, 0.31, 0.14]
    V = []; Wt = []
    for t, f in zip(st, fr):
        r = rm * f
        for k in range(nseg):
            ang = 2.0 * math.pi * k / nseg
            p = JV + AX * t + (E1 * math.cos(ang) + E2 * math.sin(ang)) * r
            V.append(p)
            Wt.append(min(1.0, max(0.5, 0.5 + t / 0.06)))
    pole = JV + AX * (t0 + tmax + 0.012)
    V.append(pole); Wt.append(1.0)
    # pull vertices that sit outside the skin back in
    for i, p in enumerate(V):
        loc, nor, idx, dd = bvhSkin.find_nearest(Vector(p))
        if dd < 0.030:
            d = float(np.dot(np.array(p) - np.array(loc), np.array(nor)))
            if d > -inside:
                V[i] = np.array(loc, dtype=np.float64) - np.array(nor, dtype=np.float64) * inside
    F = []
    nr = len(st)
    for ri in range(nr - 1):
        b0 = ri * nseg; b1 = (ri + 1) * nseg
        for k in range(nseg):
            k2 = (k + 1) % nseg
            F.append((b0 + k, b0 + k2, b1 + k2, b1 + k))
    last = (nr - 1) * nseg
    pi = len(V) - 1
    for k in range(nseg):
        k2 = (k + 1) % nseg
        F.append((last + k, last + k2, pi))
    return np.array(V), np.array(Wt), F


def skinM(bend):
    JL.clear_pose(arm)
    JL.set_rot(arm, CHILD, np.array(c['a1']), bend)
    bpy.context.view_layer.update()
    Ms = {}
    for nm in (CHILD, PAR):
        Ms[nm] = (arm.matrix_world @ arm.pose.bones[nm].matrix @ arm.data.bones[nm].matrix_local.inverted() @ arm.matrix_world.inverted())
    dg = bpy.context.evaluated_depsgraph_get()
    obe = body.evaluated_get(dg)
    m2 = obe.to_mesh()
    V = np.empty(len(m2.vertices) * 3); m2.vertices.foreach_get('co', V)
    V = V.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
    obe.to_mesh_clear()
    return Ms, V


def deform(V, Wt, Ms):
    out = np.zeros_like(V)
    for nm, M in Ms.items():
        M4 = np.array(M)
        P = V @ M4[:3, :3].T + M4[:3, 3]
        if nm == CHILD:
            w = Wt
        else:
            w = 1.0 - Wt
        out += P * w[:, None]
    return out


def view_basis(suf):
    dv = Vector(c[suf]).normalized()
    cloc = Vector(J) + dv * 6.0
    qq = (Vector(J) - cloc).normalized().to_track_quat('-Z', 'Y')
    M4 = qq.to_matrix()
    rgt = np.array(M4.col[0], dtype=np.float64); upp = np.array(M4.col[1], dtype=np.float64)
    fw2 = -np.array(M4.col[2], dtype=np.float64)
    return np.array(cloc), rgt, upp, fw2, float(c['scale_' + suf])


def cov(Vbody, Vfun, Ffun, suf, bend):
    Ms, _ = skinM(bend)
    # Vbody must be deformed already for this bend
    pol = len(polys)
    tB = []; oB = []
    for i, p in enumerate(polys):
        if min(p) >= SOCKMIN:
            continue
        for k in range(1, len(p) - 1):
            tB.append((p[0], p[k], p[k + 1])); oB.append(i)
    tF = []
    for f in Ffun:
        for k in range(1, len(f) - 1):
            tF.append((f[0], f[k], f[k + 1]))
    vv = [tuple(x) for x in Vbody]
    bBody = BVHTree.FromPolygons(vv, tB, all_triangles=True)
    # funnel-instantiated tree: own verts
    vf = [tuple(x) for x in Vfun]
    bF = BVHTree.FromPolygons(vf, tF, all_triangles=True)
    cloc, rgt, upp, fw2, sca = view_basis(suf)
    op = 0; nf = 0; bg = 0
    for py in range(N):
        for px in range(N):
            o = cloc + rgt * (((px + 0.5) / N - 0.5) * sca) + upp * (((py + 0.5) / N - 0.5) * sca) - fw2 * 6.0
            hf = bF.ray_cast(Vector(o), Vector(fw2), 12.0)
            hb = bBody.ray_cast(Vector(o), Vector(fw2), 12.0)
            if hb[0] is None:
                bg += 1
            if hf[0] is not None:
                df = (np.array(hf[0]) - o) @ fw2
                db = 1e9 if hb[0] is None else float((np.array(hb[0]) - o) @ fw2)
                if df < db - 1e-4:
                    nf += 1
                    if hb[0] is None:
                        op += 1
    return op, nf, bg


# ---- parameter sweep ----
cands = []
for rmf in (0.45, 0.60, 0.75, 0.90):
    for tmax in (0.045, 0.070):
        cands.append((rmf, tmax))
res = []
for (rmf, tmax) in cands:
    V, Wt, F = funnel(MED * rmf, -0.004, tmax, 1.0)
    row = dict(rm=round(MED * rmf, 4), tmax=tmax, nv=len(V))
    for bend in (0.0, 90.0):
        Ms, Vb = skinM(bend)
        Vd = deform(V, Wt, Ms)
        op, nf, bg = cov(Vb, Vd, F, 'front', bend)
        row['b%d' % int(bend)] = (op, round(100.0 * op / (N * N), 3), nf)
        print('[S] rm %.4f tmax %.3f bend%-3d opened=%d (%.3f%%) funcinview=%d' % (row['rm'], tmax, int(bend), op, 100.0 * op / (N * N), nf), flush=True)
    res.append(row)
json.dump(res, open(os.path.join(os.path.dirname(OUTJ), 'v2_sweep.json'), 'w'), indent=1)
print('[S] sweep done', flush=True)
