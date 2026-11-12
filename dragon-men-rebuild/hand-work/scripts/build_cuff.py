
# -*- coding: utf-8 -*-
"""Build 24 finger-joint sleeve geometry (transition cuffs) into DragonMan_Body.
Reads  std-rig/DragonMan_Std_TPose.blend, writes hand-work/ark/DragonMan_Hands_joint.blend
Only ADDS verts/faces; never touches existing verts, weights, UVs, materials.
Ring = shrink-wrap of the local skin cross-section, 5 rings x 12 segments + 2 poles.
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

SRC = r'D:\ai\建模\dragon-men-rebuild\std-rig\DragonMan_Std_TPose.blend'
OUTDIR = r'D:\ai\建模\dragon-men-rebuild\hand-work\ark'
DST = os.path.join(OUTDIR, 'DragonMan_Hands_joint.blend')
REP = r'D:\ai\建模\dragon-men-rebuild\hand-work\verify\build_report.json'

NSEG = 12
STATIONS = (-0.36, -0.12, 0.0, 0.14, 0.34)
WTS = (0.0, 0.22, 0.5, 0.78, 1.0)
RFAC = 1.06
RMIN, RMAX = 0.012, 0.048
POLE_GAP = 0.006
K1_LP = 0.55
FING = ('Thumb', 'Index', 'Middle', 'Ring')
SIDES = (('Left', 'L'), ('Right', 'R'))


def w2l(MWi, p):
    q = MWi @ Vector((p[0], p[1], p[2], 1.0))
    return Vector((q[0], q[1], q[2]))


def perp_basis(u):
    u = Vector(u)
    a = Vector((0, 0, 1))
    if abs(u.dot(a)) > 0.9:
        a = Vector((0, 1, 0))
    v = u.cross(a).normalized()
    w = u.cross(v).normalized()
    return np.array(v), np.array(w)


bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
body = bpy.data.objects['DragonMan_Body']
me = body.data
assert me.shape_keys is None
MW = np.array(body.matrix_world)
MWi = Matrix(body.matrix_world).inverted()
n0v, n0p = len(me.vertices), len(me.polygons)

co = np.empty(n0v * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
PW = co @ MW[:3, :3].T + MW[:3, 3]

skin_i = [m.name for m in me.materials].index('DragonMan_Skin')
vmat = np.zeros(n0v, dtype=np.int32)
for p in me.polygons:
    for vi in p.vertices:
        vmat[vi] = p.material_index
skin_v = np.where(vmat == skin_i)[0]
grp_name = {g.index: g.name for g in body.vertex_groups}
domname = np.empty(n0v, dtype=object)
for v in me.vertices:
    if len(v.groups):
        bg = max(v.groups, key=lambda g: g.weight).group
        domname[v.index] = grp_name.get(bg, '')
    else:
        domname[v.index] = ''
polys = [tuple(p.vertices) for p in me.polygons if p.material_index == skin_i]
skin_bvh = BVHTree.FromPolygons([tuple(PW[i]) for i in range(n0v)], polys, all_triangles=False)
print('[i] skin polys', len(polys), 'skin verts', len(skin_v))


def ring_of(c0, u, bone_set, nseg=NSEG, anchor=None):
    """Shrink-wrap ring: local skin centroid + per-angle outward skin radius.
    anchor: a point that must end up strictly inside the ring (the joint head)."""
    v, w = perp_basis(u)
    slab = 0.008
    for _ in range(2):
        rel = PW - c0
        ax = np.abs(rel @ u)
        rr = np.linalg.norm(rel - np.outer(rel @ u, u), axis=1)
        m = (ax < slab) & (rr < 0.055)
        if m.sum() >= 6:
            break
        slab *= 1.8
    c = c0.copy()
    if m.sum() >= 4:
        c = c0 + (np.mean(PW[m], axis=0) - c0)
        off = c - c0
        n = np.linalg.norm(off)
        if n > 0.02:
            c = c0 + off * (0.02 / n)
    ds = []
    for i in range(nseg):
        a = 2 * math.pi * i / nseg
        d = math.cos(a) * v + math.sin(a) * w
        loc, nor, idx, dist = skin_bvh.ray_cast(Vector(c), Vector(d), 0.06)
        ds.append(float(dist) if (loc is not None and dist > 1e-4) else None)
    val = [d for d in ds if d is not None]
    med = float(np.median(val)) if val else 0.02
    rs = []
    for d in ds:
        r = med if d is None else d
        r = min(max(r, 0.55 * med), 1.35 * med)
        r = min(max(RFAC * r, RMIN), RMAX)
        rs.append(r)
    # circular smoothing to kill cusps from the per-direction clamps
    rs = [0.5 * rs[i] + 0.25 * rs[(i - 1) % nseg] + 0.25 * rs[(i + 1) % nseg] for i in range(nseg)]
    if anchor is not None:
        dp = float(np.linalg.norm(np.asarray(anchor) - c))
        rs = [max(r, dp + 0.006) for r in rs]
    return c, rs, int(m.sum()), med, float(np.linalg.norm(np.asarray(c0) - c))


J_out = []
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()

jobs = []
for side, tag in SIDES:
    for f in FING:
        for k in (1, 2, 3):
            nm = 'mixamorig:%sHand%s%d' % (side, f, k)
            par = ('mixamorig:%sHand' % side) if k == 1 else ('mixamorig:%sHand%s%d' % (side, f, k - 1))
            jobs.append((side, tag, f, k, nm, par))

new_vert_map = []
for (side, tag, f, k, nm, par) in jobs:
    b = arm.data.bones[nm]
    pb = arm.data.bones[par]
    J = np.array(list(arm.matrix_world @ b.head_local))
    Tl = np.array(list(arm.matrix_world @ b.tail_local))
    u = Tl - J
    Lc = float(np.linalg.norm(u))
    u = u / Lc
    if k == 1:
        Lp = K1_LP * Lc
    else:
        Ph = np.array(list(arm.matrix_world @ pb.head_local))
        Lp = float(np.linalg.norm(J - Ph))
        if Lp < 1e-6:
            Lp = K1_LP * Lc
    ss = [STATIONS[0] * Lp, STATIONS[1] * Lp, 0.0, STATIONS[3] * Lc, STATIONS[4] * Lc]
    bone_set = {nm, par}
    rings = [ring_of(J + s * u, u, bone_set, anchor=J if i == 2 else None) for i, s in enumerate(ss)]
    v, w = perp_basis(u)
    ringv = []
    for (c, rs, nv, med, coff) in rings:
        rv = []
        for i in range(NSEG):
            a = 2 * math.pi * i / NSEG
            p = c + rs[i] * (math.cos(a) * v + math.sin(a) * w)
            rv.append(bm.verts.new(w2l(MWi, p)))
        ringv.append(rv)
    pole0 = bm.verts.new(w2l(MWi, rings[0][0] - u * POLE_GAP))
    pole1 = bm.verts.new(w2l(MWi, rings[4][0] + u * POLE_GAP))
    bm.verts.ensure_lookup_table()
    nf0 = len(bm.faces)
    for ri in range(4):
        A, B = ringv[ri], ringv[ri + 1]
        for i in range(NSEG):
            j = (i + 1) % NSEG
            fc = bm.faces.new((A[i], A[j], B[j], B[i]))
            fc.smooth = True
            fc.material_index = skin_i
    for i in range(NSEG):
        j = (i + 1) % NSEG
        fc = bm.faces.new((ringv[0][j], ringv[0][i], pole0))
        fc.smooth = True
        fc.material_index = skin_i
        fc = bm.faces.new((ringv[4][i], ringv[4][j], pole1))
        fc.smooth = True
        fc.material_index = skin_i
    bm.faces.ensure_lookup_table()
    wv = []
    for wt in WTS:
        wv.extend([wt] * NSEG)
    wv.append(0.0)
    wv.append(1.0)
    new_vert_map.append(dict(side=side, tag=tag, f=f, k=k, bone=nm, par=par, wc=wv,
                             rings=[(round(ss[i], 6), [float(x) for x in rings[i][0]],
                                     [round(x, 6) for x in rings[i][1]], rings[i][2], round(rings[i][3], 6),
                                     round(rings[i][4], 6)) for i in range(5)],
                             nface=len(bm.faces) - nf0, u=[float(x) for x in u],
                             J=[float(x) for x in J], Lp=Lp, Lc=Lc))
    print('[i] %s%s%d r=%s nf=%d' % (tag, f, k, [round(float(np.mean(r[1])), 4) for r in rings], len(bm.faces) - nf0))

bm.to_mesh(me)
bm.free()
me.update()
nv1 = len(me.vertices)
npol = len(me.polygons)
print('[i] verts %d -> %d (+%d)  polys %d -> %d (+%d)' % (n0v, nv1, nv1 - n0v, n0p, npol, npol - n0p))
assert nv1 - n0v == 62 * 24, (nv1 - n0v)

for gi, jd in enumerate(new_vert_map):
    base = n0v + gi * 62
    gc = body.vertex_groups.get(jd['bone']) or body.vertex_groups.new(name=jd['bone'])
    gp = body.vertex_groups.get(jd['par']) or body.vertex_groups.new(name=jd['par'])
    for n, wt in zip(range(base, base + 62), jd['wc']):
        if wt > 1e-9:
            gc.add([n], wt, 'REPLACE')
        if 1.0 - wt > 1e-9:
            gp.add([n], 1.0 - wt, 'REPLACE')

coall = np.empty(nv1 * 3)
me.vertices.foreach_get('co', coall)
coall = coall.reshape(-1, 3)

uvlayers = [l.name for l in me.uv_layers]
vert_uv = {}
for lname in uvlayers:
    lay = me.uv_layers[lname]
    arr = np.zeros(len(me.loops) * 2)
    lay.data.foreach_get('uv', arr)
    arr = arr.reshape(-1, 2)
    per_v = np.zeros((nv1, 2))
    seen = np.zeros(nv1, dtype=bool)
    for li, lp in enumerate(me.loops):
        vi = lp.vertex_index
        if not seen[vi]:
            per_v[vi] = arr[li]
            seen[vi] = True
    vert_uv[lname] = per_v

uv_report = []
for gi, jd in enumerate(new_vert_map):
    J = np.array(jd['J'])
    child, par = jd['bone'], jd['par']
    cand = [i for i in skin_v if domname[i] == child and np.linalg.norm(PW[i] - J) < 0.06]
    if len(cand) < 4:
        cand = [i for i in skin_v if domname[i] in (child, par) and np.linalg.norm(PW[i] - J) < 0.09]
    if len(cand) < 4:
        cand = [i for i in skin_v if domname[i] in (child, par) and np.linalg.norm(PW[i] - J) < 0.16]
    kd = KDTree(len(cand))
    for n, i in enumerate(cand):
        kd.insert(Vector(co[i]), n)
    kd.balance()
    base = n0v + gi * 62
    srcidx, dbones = {}, {}
    for vi in range(base, base + 62):
        _, n, _ = kd.find(Vector(coall[vi]))
        si = cand[n]
        srcidx[vi] = si
        dbones[domname[si]] = dbones.get(domname[si], 0) + 1
    for lname in uvlayers:
        lay = me.uv_layers[lname]
        pv = vert_uv[lname]
        for lp in me.loops:
            if base <= lp.vertex_index < base + 62:
                lay.data[lp.index].uv = Vector(pv[srcidx[lp.vertex_index]])
    uv_report.append(dict(ncand=len(cand), src=dbones))

mat_tally = {}
for p in me.polygons:
    if p.index >= n0p:
        nmx = me.materials[p.material_index].name
        mat_tally[nmx] = mat_tally.get(nmx, 0) + 1
tris_new = sum((len(p.vertices) - 2) for p in me.polygons if p.index >= n0p)
bad = 0
for n in range(n0v, nv1):
    s = sum(g.weight for g in me.vertices[n].groups)
    if abs(s - 1.0) > 1e-6 or len(me.vertices[n].groups) > 4:
        bad += 1
print('[i] new faces by material', mat_tally, 'new tris', tris_new, 'bad wsum/ninf', bad)


# ---- per-joint rest containment of the joint head inside its own shell ----
MINV = np.empty(nv1 * 3)
me.vertices.foreach_get('co', MINV)
MINV = MINV.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
fib = []
GA = math.pi * (3 - math.sqrt(5))
for i in range(26):
    z = 1 - 2 * (i + 0.5) / 26
    r = math.sqrt(max(0.0, 1 - z * z))
    th = GA * i
    fib.append(Vector((r * math.cos(th), r * math.sin(th), z)))
shells = []
for gi, jd in enumerate(new_vert_map):
    base = n0v + gi * 62
    vv = [tuple(MINV[i]) for i in range(base, base + 62)]
    ff = [tuple(v - base for v in me.polygons[pi].vertices) for pi in range(n0p, npol) if base <= me.polygons[pi].vertices[0] < base + 62]
    shells.append(BVHTree.FromPolygons(vv, ff, all_triangles=False))
try:
    from mathutils.bvhtree import BVHTree
except Exception:
    pass


def nfc(act):
    c = 0
    for lay in getattr(act, 'layers', []):
        for st in lay.strips:
            for cb in getattr(st, 'channelbags', []):
                c += len(cb.fcurves)
    return c


act = arm.animation_data.action if arm.animation_data else None
print('[i] action', act.name if act else None, 'fcurves', nfc(act) if act else 0)

cont = []
for gi, jd in enumerate(new_vert_map):
    J = np.array(jd['J'])
    h = 0
    for d in fib:
        loc, nor, idx, dist = shells[gi].ray_cast(Vector(J), d, 0.12)
        if loc is not None:
            h += 1
    cont.append(h)
print('[i] rest containment (26 dirs, own shell):', cont)
print('[i] joints with incomplete containment:', [new_vert_map[i]['bone'] for i, h in enumerate(cont) if h < 26])
rep = dict(nseg=NSEG, nverts_new=nv1 - n0v, containment=cont, nfaces_new=npol - n0p, tris_new=tris_new,
           materials=mat_tally, uvlayers=uvlayers, bad_wsum=bad,
           action=(act.name if act else None), fcurves=(nfc(act) if act else 0),
           joints=[{**{kk: vv for kk, vv in jd.items() if kk != 'wc'}, **uv_report[i], 'contain': cont[i]}
                    for i, jd in enumerate(new_vert_map)])
os.makedirs(OUTDIR, exist_ok=True)
os.makedirs(os.path.dirname(REP), exist_ok=True)
with open(REP, 'w', encoding='utf-8') as fh:
    json.dump(rep, fh, indent=1, ensure_ascii=False)
bpy.ops.wm.save_as_mainfile(filepath=DST)
print('[ok] saved', DST)
