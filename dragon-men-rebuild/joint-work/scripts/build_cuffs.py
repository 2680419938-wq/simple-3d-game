# -*- coding: utf-8 -*-
"""Build body-joint transition cuffs (shoulder/elbow/wrist/hip/neck/waist) into DragonMan_Body.
Method = the accepted finger-cuff method (hand-work/scripts/build_cuff.py), generalized:
tube on the CHILD bone axis, 5 rings, per-angle shrink-wrapped radius from the Skin-only BVH,
clamped [0.62,1.35]*local_median*1.06 -> [0.012,RMAX], one circular smoothing pass, and the
joint head J forced inside every ring (r_i = max(r_i, |J-c_perp|+0.006)).
Only ADDS verts/faces; never touches existing verts, weights, UVs, materials.
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\joint-work\scripts')
import jlib as JL

SRC = r'D:\ai\建模\dragon-men-rebuild\hand-work\ark\DragonMan_Hands_joint.blend'
OUTDIR = r'D:\ai\建模\dragon-men-rebuild\joint-work'
DST = os.path.join(OUTDIR, 'DragonMan_Joint_full.blend')
REP = os.path.join(OUTDIR, 'verify', 'build_report.json')

# joints to build (baseline < 100%): 8 limb joints + neck + 2 waist levels
BUILD = ['L_shoulder', 'R_shoulder', 'L_elbow', 'R_elbow', 'L_wrist', 'R_wrist',
         'L_hip', 'R_hip', 'neck', 'waist', 'waist1']
# round 2 (after rest-pose renders): hips keep only the inner socket (outer sleeve showed
# through fur/armor at rest); waist is dropped (belt gap sliver -> cuff visible at rest).
SLEEVELESS = {'L_hip', 'R_hip'}
SKIP = {'waist'}
BUILD = [k for k in BUILD if k not in SKIP]

WTS = (0.0, 0.22, 0.5, 0.78, 1.0)
RFAC = 1.06
RMIN = 0.012
POLE_GAP = 0.006
C_LO, C_HI = 0.62, 1.35
ANCH = 0.006
INFO = {k: (cb, pb) for k, cb, pb, tw in JL.JOINTS}


def perp_basis(u):
    u = Vector(u)
    a = Vector((0, 0, 1))
    if abs(u.dot(a)) > 0.9:
        a = Vector((0, 1, 0))
    v = u.cross(a).normalized()
    w = u.cross(v).normalized()
    return np.array(v), np.array(w)


def w2l(MWi, p):
    q = MWi @ Vector((p[0], p[1], p[2], 1.0))
    return Vector((q[0], q[1], q[2]))


bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
# neutralize the action (do NOT drop it: the GLB needs its animation channels) so every
# measurement below is taken in the REST pose, then re-link it before saving.
ACT = arm.animation_data.action if arm.animation_data else None
if ACT is not None:
    arm.animation_data.action = None
JL.clear_pose(arm)
bpy.context.view_layer.update()
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
skin_i = [m.name for m in me.materials].index(JL.SKIN)
objs = [bpy.data.objects[n] for n in JL.MESHES]
dg = bpy.context.evaluated_depsgraph_get()
skin_bvh = JL.obj_bvh(objs, dg, mat_filter={JL.SKIN})

# every incident poly must be Skin -> clean UV donors
vskin = np.ones(n0v, dtype=bool)
vall = np.zeros(n0v, dtype=bool)
for p in me.polygons:
    isk = (p.material_index == skin_i)
    for vi in p.vertices:
        vall[vi] = True
        if not isk:
            vskin[vi] = False
vskin = vskin & vall
grp_name = {g.index: g.name for g in body.vertex_groups}
domname = np.empty(n0v, dtype=object)
for v in me.vertices:
    if len(v.groups):
        bg = max(v.groups, key=lambda g: g.weight)
        domname[v.index] = grp_name.get(bg.group, '')
    else:
        domname[v.index] = ''
print('[B] skin-clean verts %d / %d' % (int(vskin.sum()), n0v))
polys = [tuple(p.vertices) for p in me.polygons if p.material_index == skin_i]
print('[B] skin polys', len(polys))


def ring_of(c0, u, med, bone_mask, Janchor):
    v, w = perp_basis(u)
    slab = max(0.008, 0.30 * med)
    rr_lim = max(0.055, 2.2 * med)
    rel = PW - c0
    ax = np.abs(rel @ u)
    rr = np.linalg.norm(rel - np.outer(rel @ u, u), axis=1)
    m = None
    for it in range(4):
        m = (ax < slab) & (rr < rr_lim) & bone_mask
        if m.sum() >= 6:
            break
        m2 = (ax < slab) & (rr < rr_lim)
        if m.sum() < 6 and m2.sum() >= 6:
            m = m2
            break
        slab *= 1.7
        rr_lim *= 1.25
    c = c0.copy()
    if m is not None and m.sum() >= 4:
        c = c0 + (np.mean(PW[m], axis=0) - c0)
        off = c - c0
        n = float(np.linalg.norm(off))
        if n > 0.35 * med:
            c = c0 + off * (0.35 * med / n)
    rmax_ray = max(0.06, 2.6 * med)
    ds = []
    for i in range(NSEG):
        a = 2 * math.pi * i / NSEG
        d = math.cos(a) * v + math.sin(a) * w
        loc, nor, idx, dist = skin_bvh.ray_cast(Vector(c), Vector(d), rmax_ray)
        ds.append(float(dist) if (loc is not None and dist > 1e-4) else None)
    val = [d for d in ds if d is not None]
    medr = float(np.median(val)) if val else med
    rs = []
    for d in ds:
        r = medr if d is None else d
        r = min(max(r, C_LO * medr), C_HI * medr)
        r = min(max(RFAC * r, RMIN), RMAX)
        rs.append(r)
    rs = [0.5 * rs[i] + 0.25 * rs[(i - 1) % NSEG] + 0.25 * rs[(i + 1) % NSEG] for i in range(NSEG)]
    dv = np.asarray(Janchor) - c
    dp = float(np.linalg.norm(dv - (dv @ u) * u))
    rs = [min(max(r, dp + ANCH), RMAX) for r in rs]
    return c, rs, int(0 if m is None else m.sum()), medr, float(np.linalg.norm(np.asarray(c0) - c))


J_out = []
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()
newrec = []
for key in BUILD:
    WITHSLEEVE = key not in SLEEVELESS
    cb, pbp = INFO[key]
    Jw, Ct = JL.bh(arm, cb)
    Pw, _ = JL.bh(arm, pbp)
    u = JL.unit(Ct - Jw)
    Lc = float(np.linalg.norm(Ct - Jw))
    Lp = float(np.linalg.norm(Jw - Pw))
    # local median skin radius in the ring plane through J
    vv, ww = perp_basis(u)
    ds = []
    for i in range(24):
        a = 2 * math.pi * i / 24
        d = math.cos(a) * vv + math.sin(a) * ww
        loc, nor, idx, dist = skin_bvh.ray_cast(Vector(Jw), Vector(d), 1.0)
        if loc is not None and dist > 1e-4:
            ds.append(dist)
    med = float(np.median(ds)) if ds else 0.02
    NSEG = 16 if med > 0.05 else 12
    RMAX = max(0.048, 1.5 * med)
    h_neg = min(0.42 * Lp, 1.5 * med, 0.10)
    h_pos = min(0.45 * Lc, 1.5 * med, 0.12)
    ss = [-h_neg, -0.30 * h_neg, 0.0, 0.40 * h_pos, h_pos]
    bone_mask = np.isin(domname, [cb, pbp])
    s0 = len(bm.verts)
    nf0 = len(bm.faces)
    if WITHSLEEVE:
        rings = [ring_of(Jw + s * u, u, med, bone_mask, Jw) for s in ss]
        v, w = perp_basis(u)
        ringv = []
        for (c, rs, nv, medr, coff) in rings:
            rv = []
            for i in range(NSEG):
                a = 2 * math.pi * i / NSEG
                p = c + rs[i] * (math.cos(a) * v + math.sin(a) * w)
                rv.append(bm.verts.new(w2l(MWi, p)))
            ringv.append(rv)
        pole0 = bm.verts.new(w2l(MWi, rings[0][0] - u * POLE_GAP))
        pole1 = bm.verts.new(w2l(MWi, rings[4][0] + u * POLE_GAP))
        bm.verts.ensure_lookup_table()
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

    else:
        rings = []
    b0 = len(bm.verts)
    bf0 = len(bm.faces)
    # socket must stay INSIDE the skin: derive it from the thinnest of 26 radial skin
    # distances at J (round 2b: the 0.052 sphere poked out of the open crotch at rest).
    dmin = 0.5
    dn = u.copy()
    _ga = math.pi * (3 - math.sqrt(5))
    for _i in range(26):
        _z = 1 - 2 * (_i + 0.5) / 26
        _r = math.sqrt(max(0.0, 1 - _z * _z))
        d = Vector((_r * math.cos(_ga * _i), _r * math.sin(_ga * _i), _z))
        loc, nor, idx, dist = skin_bvh.ray_cast(Vector(Jw), Vector(d), 0.5)
        if loc is not None and dist > 1e-4 and dist < dmin:
            dmin = dist
            dn = d.copy()
    SOCK = max(0.012, min(0.052, 0.95 * med, 0.85 * dmin))
    FLAT = None
    if key in SLEEVELESS:
        SOCK = min(SOCK, 0.030)
        FLAT = dn   # flatten along the thinnest skin direction (open crotch gap)
    # sit the socket slightly down the child bone so its thin side retreats from the
    # open crotch gap; J stays inside because |CS-J| = 0.45*SOCK <= SOCK
    SC = Jw + 0.45 * SOCK * u

    def sockp(off):
        if FLAT is not None:
            off = off - 0.85 * off.dot(FLAT) * FLAT
        return w2l(MWi, SC + off)
    NRS = 5
    tw, sw = perp_basis(u)
    rows = []
    for k in range(1, NRS + 1):
        ph = math.pi * k / (NRS + 1)
        cz, sr = math.cos(ph), math.sin(ph)
        rv = []
        for i in range(NSEG):
            a = 2 * math.pi * i / NSEG
            off = SOCK * (cz * u + sr * (math.cos(a) * tw + math.sin(a) * sw))
            rv.append(bm.verts.new(sockp(off)))
        rows.append(rv)
    btop = bm.verts.new(sockp(SOCK * u))
    bbot = bm.verts.new(sockp(-SOCK * u))
    for i in range(NSEG):
        j = (i + 1) % NSEG
        fc = bm.faces.new((btop, rows[0][i], rows[0][j]))
        fc.smooth = True
        fc.material_index = skin_i
        for k in range(NRS - 1):
            fc = bm.faces.new((rows[k][i], rows[k][j], rows[k + 1][j], rows[k + 1][i]))
            fc.smooth = True
            fc.material_index = skin_i
        fc = bm.faces.new((bbot, rows[NRS - 1][j], rows[NRS - 1][i]))
        fc.smooth = True
        fc.material_index = skin_i
    wsock = []
    for k in range(1, NRS + 1):
        ph = math.pi * k / (NRS + 1)
        ws = max(0.0, min(1.0, 0.5 + 0.5 * math.cos(ph)))
        wsock.extend([ws] * NSEG)
    wsock.append(1.0)
    wsock.append(0.0)
    bm.faces.ensure_lookup_table()
    nvs = b0 - s0
    nvb = len(bm.verts) - b0
    nfb = len(bm.faces) - bf0
    nvp = nvs + nvb
    wc = []
    if WITHSLEEVE:
        for wt in WTS:
            wc.extend([wt] * NSEG)
        wc.append(0.0)
        wc.append(1.0)
    wc = wc + wsock
    newrec.append(dict(key=key, bone=cb, par=pbp, nseg=NSEG, nring=5, nvp=nvp, nv_s=nvs,
                       sock=dict(R=round(SOCK, 6), nseg=NSEG, nring=NRS + 1, nvp=nvb, nf=nfb, wts=wsock),
                       h_neg=round(h_neg, 6), h_pos=round(h_pos, 6), med=round(med, 6),
                       RMAX=round(RMAX, 6), wc=wc, J=[float(x) for x in Jw], u=[float(x) for x in u],
                       Lp=round(Lp, 6), Lc=round(Lc, 6),
                       rings=[(round(ss[i], 6), float(np.min(rings[i][1])), float(np.mean(rings[i][1])),
                               float(np.max(rings[i][1])), rings[i][2], round(rings[i][3], 6),
                               round(rings[i][4], 6)) for i in range(5)] if rings else []))
    if rings:
        rmin = min(min(r[1]) for r in rings)
        rmean = float(np.mean([np.mean(r[1]) for r in rings]))
        rmax = max(max(r[1]) for r in rings)
    else:
        rmin = rmean = rmax = 0.0
    print('[B] %-11s nseg=%2d med=%.4f h=%.3f/%.3f rmin=%.4f rmean=%.4f rmax=%.4f sock=%.4f nf=%d/%d' % (
        key, NSEG, med, h_neg, h_pos, rmin, rmean, rmax, SOCK, len(bm.faces) - nf0 - nfb, nfb), flush=True)

bm.to_mesh(me)
bm.free()
me.update()
nv1 = len(me.vertices)
npol = len(me.polygons)
print('[B] verts %d -> %d (+%d)  polys %d -> %d (+%d)' % (n0v, nv1, nv1 - n0v, n0p, npol, npol - n0p))
assert nv1 - n0v == sum(r['nvp'] for r in newrec)

# weights
off = n0v
for jd in newrec:
    gc = body.vertex_groups.get(jd['bone']) or body.vertex_groups.new(name=jd['bone'])
    gp = body.vertex_groups.get(jd['par']) or body.vertex_groups.new(name=jd['par'])
    for n, wt in zip(range(off, off + jd['nvp']), jd['wc']):
        if wt > 1e-9:
            gc.add([n], wt, 'REPLACE')
        if 1.0 - wt > 1e-9:
            gp.add([n], 1.0 - wt, 'REPLACE')
    jd['base'] = off
    off += jd['nvp']

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

for jd in newrec:
    base = jd['base']
    Jn = np.array(jd['J'])
    child, par = jd['bone'], jd['par']
    cand = [i for i in np.where(vskin)[0] if domname[i] in (child, par) and np.linalg.norm(PW[i] - Jn) < max(0.06, 1.5 * jd['med'])]
    if len(cand) < 4:
        cand = [i for i in np.where(vskin)[0] if domname[i] in (child, par) and np.linalg.norm(PW[i] - Jn) < 0.10]
    if len(cand) < 4:
        cand = [i for i in np.where(vskin)[0] if domname[i] in (child, par) and np.linalg.norm(PW[i] - Jn) < 0.20]
    if len(cand) < 4:
        raise RuntimeError('no skin UV donor for %s' % jd['key'])
    kd = KDTree(len(cand))
    for n, i in enumerate(cand):
        kd.insert(Vector(co[i]), n)
    kd.balance()
    srcidx, dbones = {}, {}
    for vi in range(base, base + jd['nvp']):
        _, n, _ = kd.find(Vector(coall[vi]))
        si = cand[n]
        srcidx[vi] = si
        dbones[domname[si]] = dbones.get(domname[si], 0) + 1
    for lname in uvlayers:
        lay = me.uv_layers[lname]
        pv = vert_uv[lname]
        for lp in me.loops:
            if base <= lp.vertex_index < base + jd['nvp']:
                lay.data[lp.index].uv = Vector(pv[srcidx[lp.vertex_index]])
    jd['uv'] = dict(ncand=len(cand), src=dbones, all_skin=bool(all(vskin[i] for i in cand)))
    print('[B] %-11s uv donors=%d %s' % (jd['key'], len(cand), dbones), flush=True)

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
print('[B] new faces by mat', mat_tally, 'tris', tris_new, 'bad wsum/ninf', bad)

# rest containment of J inside each new shell (26 directions)
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
cont = []
for jd in newrec:
    base = jd['base']
    n = jd['nvp']
    nvs = jd['nv_s']
    vv = [tuple(MINV[i]) for i in range(base, base + n)]
    parts = [('socket', nvs, n, 0.06)]
    if nvs > 0:
        parts.insert(0, ('sleeve', 0, nvs, max(0.05, 4.0 * jd['med'])))
    else:
        jd['contain_sleeve'] = None
        jd['nf_sleeve'] = 0
    for tag, lo, hi, rmax in parts:
        ff = []
        for pi in range(n0p, npol):
            vs = me.polygons[pi].vertices
            mn, mx = min(vs) - base, max(vs) - base
            if mn >= lo and mx < hi:
                ff.append(tuple(v - base for v in vs))
        sh = BVHTree.FromPolygons(vv, ff, all_triangles=False)
        h = 0
        for d in fib:
            loc, nor, idx, dist = sh.ray_cast(Vector(jd['J']), d, rmax)
            if loc is not None:
                h += 1
        jd['contain_' + tag] = h
        jd['nf_' + tag] = len(ff)
    cont.append((jd['key'], jd['contain_sleeve'], jd['contain_socket']))
    jd['contain'] = jd['contain_socket']
print('[B] containment 26 dirs (sleeve/socket):', cont)
assert all(c[2] == 26 for c in cont), 'socket does not enclose J'

JL.clear_pose(arm)
if ACT is not None:
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = ACT
    try:
        sl = ACT.slots[0]
        arm.animation_data.action_slot = sl
    except Exception as e:
        print('[B] slot warn', e)
    print('[B] action restored', ACT.name, 'users', ACT.users)
act = arm.animation_data.action if arm.animation_data else None
rep = dict(src=SRC, nseg_note='12 if local median skin radius <= 0.05 else 16', wts=WTS, rfac=RFAC,
           rmin=RMIN, pole_gap=POLE_GAP, clamp=[C_LO, C_HI], anchor=ANCH,
           nverts_new=nv1 - n0v, nfaces_new=npol - n0p, tris_new=tris_new, materials=mat_tally,
           bad_wsum=bad, containment=[jd['contain'] for jd in newrec],
           uvlayers=[str(l) for l in uvlayers],
           action=(act.name if act else None), joints=newrec)
os.makedirs(os.path.dirname(REP), exist_ok=True)
json.dump(rep, open(REP, 'w', encoding='utf-8'), indent=1, default=float)
bpy.ops.wm.save_as_mainfile(filepath=DST)
print('[B] saved', DST, os.path.getsize(DST))