# -*- coding: utf-8 -*-
r"""m1: v2b base + knee joint sleeves (L/R) -> DragonMan_Std_TPose.blend
Sleeve geometry/weights ported from armor-work\scripts\cuff_build2.py (accepted params).
UV: MLS transfer from Skin donors above the knee (joint-work\scripts\uv_fix.py style).
Then rotate scene roots +90 deg about Z so glTF arms run along +-X (Mixamo/glTF standard).
"""
import bpy, bmesh, sys, json, math, os
import numpy as np
from mathutils import Vector, Matrix

SRC = r'D:\ai\建模\dragon-men-rebuild\joint-work\v2b\DragonMan_Joint_v2b.blend'
DST = r'D:\ai\建模\dragon-men-rebuild\joint-work\merge\DragonMan_Std_TPose.blend'
REPORT = r'D:\ai\建模\dragon-men-rebuild\joint-work\merge\reports\m1_cuffs.json'
os.makedirs(os.path.dirname(REPORT), exist_ok=True)

NSEG = 12; FLOOR = 0.055; BBAND = -0.03
S_RINGS = [-0.20, 0.15, 0.50, 0.85, 1.20]
PREF_MAT = 'Skin'  # matched by suffix against DragonMan_Skin
RIDGE = 1e-3
BONE = {'L': ('mixamorig:LeftUpLeg', 'mixamorig:LeftLeg', 'mixamorig:LeftFoot'),
        'R': ('mixamorig:RightUpLeg', 'mixamorig:RightLeg', 'mixamorig:RightFoot')}

bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']; body = bpy.data.objects['DragonMan_Body']
feet = {s: bpy.data.objects['DragonMan_Foot.' + s] for s in 'LR'}
MWa = np.array(arm.matrix_world)
R = {'src': SRC, 'dst': DST, 'params': {'nseg': NSEG, 'floor': FLOOR, 'rings': S_RINGS, 'mat': PREF_MAT, 'bband': BBAND},
     'parents': {o.name: (o.parent.name if o.parent else None) for o in (body, feet['L'], feet['R'], arm)}, 'sides': {}}

def raw_world(ob):
    me = ob.data; n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    MW = np.array(ob.matrix_world); return co @ MW[:3, :3].T + MW[:3, 3]

def ring_of(Q, tag):
    c = Q.mean(0); u, s, vt = np.linalg.svd(Q - c)
    rr = np.linalg.norm(Q - c, axis=1)
    return dict(tag=tag, n=int(len(Q)), c=c.tolist(), normal=vt[2].tolist(),
                r50=float(np.percentile(rr, 50)), r90=float(np.percentile(rr, 90)))

P_body = raw_world(body)
P_foot = {s: raw_world(feet[s]) for s in 'LR'}
K = {s: np.array(arm.matrix_world @ arm.data.bones[BONE[s][1]].head_local) for s in 'LR'}
endpts = {}
for s in 'LR':
    k = K[s]
    m = (P_body[:, 2] >= k[2]) & (P_body[:, 2] <= k[2] + 0.02) & (np.hypot(P_body[:, 0] - k[0], P_body[:, 1] - k[1]) < 0.30)
    assert m.sum() >= 8, ('thigh ring empty', s, int(m.sum()))
    A = ring_of(P_body[m], 'thigh_end')
    Pf = P_foot[s]; zb = k[2] + BBAND
    m2 = (Pf[:, 2] >= zb - 0.008) & (Pf[:, 2] <= zb + 0.008) & (np.hypot(Pf[:, 0] - k[0], Pf[:, 1] - k[1]) < 0.30)
    assert m2.sum() >= 8, ('shin band empty', s, int(m2.sum()))
    B = ring_of(Pf[m2], 'shin_band')
    endpts[s] = (A, B)
    ca, cb = np.array(A['c']), np.array(B['c']); ab = cb - ca; L = np.linalg.norm(ab); u = ab / L
    jp = k - ca
    R['sides'][s] = {'A': A, 'B': B, 'J': k.tolist(), 'dist': float(L),
                     'J_perp_to_AB': float(np.linalg.norm(jp - np.dot(jp, u) * u)), 'J_t_along_AB': float(np.dot(jp, u) / L)}
    print('[M1] %s A=%s r50=%.4f n=%d | B=%s r50=%.4f n=%d | dist=%.4f' % (
        s, np.round(ca, 3), A['r50'], A['n'], np.round(cb, 3), B['r50'], B['n'], L))

# ---- material / vert bookkeeping before edit
me = body.data; n0 = len(me.vertices); f0 = len(me.polygons)
mat_names = [m.name for m in me.materials]
_hits = [i for i, nm in enumerate(mat_names) if nm == PREF_MAT or nm.endswith('_' + PREF_MAT) or nm.endswith(PREF_MAT)]
skin_i = _hits[0] if _hits else 2
assert mat_names[skin_i].endswith(PREF_MAT), mat_names
mat_faces0 = {}
for p in me.polygons: mat_faces0[mat_names[p.material_index]] = mat_faces0.get(mat_names[p.material_index], 0) + 1
R['mat_faces_before'] = mat_faces0
R['verts_before'] = n0; R['faces_before'] = f0
tris0 = sum(len(p.vertices) - 2 for p in me.polygons)
R['tris_before'] = tris0
vskin = np.zeros(n0, dtype=bool)
for p in me.polygons:
    if p.material_index == skin_i:
        for vi in p.vertices: vskin[vi] = True
uvnames = [u.name for u in me.uv_layers]
vert_uv = {nm: {} for nm in uvnames}
for li, lp in enumerate(me.loops):
    vi = lp.vertex_index
    for nm in uvnames:
        if vi not in vert_uv[nm]: vert_uv[nm][vi] = np.array(me.uv_layers[nm].data[li].uv)

MWb = np.array(body.matrix_world); MWbi = np.linalg.inv(MWb)
bm = bmesh.new(); bm.from_mesh(me)
new_world = []
def newv(w):
    loc = (MWbi @ np.array([w[0], w[1], w[2], 1.0]))[:3]
    new_world.append([float(w[0]), float(w[1]), float(w[2])])
    return bm.verts.new(Vector(loc))

def clamp01(t): return min(1.0, max(0.0, t))
ring_info = {}; side_span = {}
for s in 'LR':
    A, B = endpts[s]; ca, cb = np.array(A['c']), np.array(B['c'])
    ab = cb - ca; L = np.linalg.norm(ab)
    na = np.array(A['normal']); na = na if na[2] > 0 else -na
    nb = np.array(B['normal']); nb = nb if nb[2] < 0 else -nb
    def center(sv):
        if sv < 0: return ca + na * (abs(sv) * L) * 0.35
        if sv > 1: return cb + nb * (max(0.0, sv - 1) * L) * 0.35
        return ca + ab * sv
    ks = np.array([-0.20, 0.00, 0.35, 0.75, 1.00, 1.20])
    kr = np.array([A['r50'] * 0.75, A['r50'] * 0.95, FLOOR, FLOOR, B['r50'] * 1.05, B['r50'] * 0.85])
    def radius(sv): return float(np.interp(sv, ks, kr))
    vs = []; per_ring = []
    for i, sv in enumerate(S_RINGS):
        c = center(sv); rr = radius(sv)
        if i == 0: tan = center(S_RINGS[1]) - c
        elif i == len(S_RINGS) - 1: tan = c - center(S_RINGS[-2])
        else: tan = center(S_RINGS[i + 1]) - center(S_RINGS[i - 1])
        tan = tan / np.linalg.norm(tan)
        ex = np.cross(tan, np.array([0.0, 0, 1.0]))
        if np.linalg.norm(ex) < 1e-4: ex = np.array([1.0, 0, 0])
        ex /= np.linalg.norm(ex); ey = np.cross(tan, ex)
        ringv = [newv(c + rr * (math.cos(2 * math.pi * j / NSEG) * ex + math.sin(2 * math.pi * j / NSEG) * ey)) for j in range(NSEG)]
        vs.append(ringv)
        jp = K[s] - c; perp = np.linalg.norm(jp - np.dot(jp, tan) * tan)
        per_ring.append({'s': sv, 'c': np.round(c, 4).tolist(), 'r': round(rr, 4), 'J_perp': round(float(perp), 4), 'containsJ': bool(perp < rr)})
    poleA = newv(center(-0.35)); poleB = newv(center(1.35))
    def face(vlist):
        f = bm.faces.new(vlist); f.smooth = True; f.material_index = skin_i; return f
    for i in range(len(vs) - 1):
        for j in range(NSEG):
            j2 = (j + 1) % NSEG
            face((vs[i][j], vs[i][j2], vs[i + 1][j2], vs[i + 1][j]))
    for j in range(NSEG):
        j2 = (j + 1) % NSEG
        face((poleA, vs[0][j2], vs[0][j]))
        face((poleB, vs[-1][j], vs[-1][j2]))
    ring_info[s] = {'rings': per_ring, 'poleA': np.round(center(-0.35), 4).tolist(), 'poleB': np.round(center(1.35), 4).tolist()}
    print('[M1] %s rings ' % s + ' | '.join('s=%.2f r=%.3f perp=%.3f %s' % (d['s'], d['r'], d['J_perp'], 'IN' if d['containsJ'] else 'OUT') for d in per_ring))
bm.normal_update(); bm.verts.index_update(); bm.faces.index_update()
bm.to_mesh(me); bm.free(); me.update()
nv = len(me.vertices) - n0; nf = len(me.polygons) - f0
R['new_verts'] = nv; R['new_faces'] = nf; R['ring_info'] = ring_info
R['verts_after'] = len(me.vertices); R['faces_after'] = len(me.polygons)
R['tris_after'] = sum(len(p.vertices) - 2 for p in me.polygons)
print('[M1] appended verts %d faces %d  total %d/%d' % (nv, nf, len(me.vertices), len(me.polygons)))

# ---- MLS UV transfer for the appended loops
nl = 4 * nf; loop_start = len(me.loops) - nl
NW = np.array(new_world)
newuv = {nm: {} for nm in uvnames}
uvstats = {}
for s in 'LR':
    k = K[s]
    cand = None
    for rr in (0.10, 0.20, 0.30):
        cand = [i for i in range(n0) if vskin[i] and P_body[i, 2] >= k[2] and np.linalg.norm(P_body[i] - k) < rr]
        if len(cand) >= 8: break
    if len(cand) < 8:
        dd = np.linalg.norm(P_body[:n0] - k, axis=1); cand = [int(i) for i in np.argsort(dd)[:48] if vskin[i]]
    C = np.array(cand, dtype=np.int64); D = P_body[C] - k; DU = {nm: np.array([vert_uv[nm][i] for i in C]) for nm in uvnames}
    base = n0 + (0 if s == 'L' else (NSEG * len(S_RINGS) + 2))
    cnt = NSEG * len(S_RINGS) + 2
    maxdev = 0.0
    for vi in range(base, base + cnt):
        w = NW[vi - n0]
        d = np.linalg.norm(D - (w - k), axis=1); kk = np.argsort(d)[:40]; dk = d[kk]
        sig = max(1e-4, float(np.median(dk))); wgt = np.exp(-(dk / sig) ** 2) + 1e-6
        X = np.hstack([np.ones((len(kk), 1)), D[kk]])
        def fit(wg, y):
            Xw = X * wg[:, None]; Am = Xw.T @ X
            lam = RIDGE * np.trace(Am) / Am.shape[0]
            Am = Am + np.eye(Am.shape[0]) * lam
            sol, *_ = np.linalg.lstsq(Am, Xw.T @ y, rcond=None); return sol
        for nm in uvnames:
            y = DU[nm][kk]; sol = fit(wgt, y)
            res = np.linalg.norm(y - X @ sol, axis=1)
            keep = res <= max(2.5 * np.median(res), 1e-6)
            if keep.sum() >= 6: sol = fit(wgt * keep, y)
            newuv[nm][vi] = sol[0] + sol[1:].T @ (w - k)
            maxdev = max(maxdev, float(np.max(np.abs(newuv[nm][vi]))))
    uvstats[s] = {'donors': int(len(C)), 'radius_used': float(np.linalg.norm(D, axis=1).max()), 'max_abs_uv': maxdev}
    print('[M1] %s MLS donors %d  radius %.3f  max|uv| %.3f' % (s, len(C), uvstats[s]['radius_used'], maxdev))
miss = 0
for li in range(loop_start, len(me.loops)):
    vi = me.loops[li].vertex_index
    for nm in uvnames:
        u = newuv[nm].get(vi)
        if u is None: miss += 1; u = (0.0, 0.0)
        me.uv_layers[nm].data[li].uv = (float(u[0]), float(u[1]))
R['uv_missing'] = miss; R['uv_stats'] = uvstats

# ---- weights
vgs = {}
for s in 'LR':
    for nm in (BONE[s][0], BONE[s][1]):
        vgs[nm] = body.vertex_groups[nm]
idx = n0
for s in 'LR':
    up, low = BONE[s][0], BONE[s][1]
    vgs[up].add([idx], 1.0, 'REPLACE'); idx += 1
    for sv in S_RINGS:
        ids = list(range(idx, idx + NSEG)); idx += NSEG
        wp = round(1.0 - clamp01(sv), 2)
        if wp > 0: vgs[up].add(ids, wp, 'REPLACE')
        if wp < 1: vgs[low].add(ids, 1.0 - wp, 'REPLACE')
    vgs[low].add([idx], 1.0, 'REPLACE'); idx += 1
ws = [(sum(g.weight for g in me.vertices[vi].groups if g.weight > 0), sum(1 for g in me.vertices[vi].groups if g.weight > 0)) for vi in range(n0, len(me.vertices))]
R['weight_sum_min'] = min(w[0] for w in ws); R['weight_sum_max'] = max(w[0] for w in ws)
R['max_influences'] = max(w[1] for w in ws); R['zero_weight_verts'] = sum(1 for w in ws if w[0] <= 0)
assert abs(R['weight_sum_min'] - 1) < 1e-6 and abs(R['weight_sum_max'] - 1) < 1e-6, R['weight_sum_min']
assert R['max_influences'] <= 4 and R['zero_weight_verts'] == 0

# ---- knee-plate islands (informational; Walk product deletes them)
import collections
adj = collections.defaultdict(set)
for e in me.edges:
    a0, b0 = int(e.vertices[0]), int(e.vertices[1]); adj[a0].add(b0); adj[b0].add(a0)
seen = set(); isl = []
for v0 in range(len(me.vertices)):
    if v0 in seen: continue
    stack = [v0]; comp = []
    seen.add(v0)
    while stack:
        v = stack.pop(); comp.append(v)
        for nb in adj[v]:
            if nb not in seen: seen.add(nb); stack.append(nb)
    isl.append(comp)
grp_names = {g.index: g.name for g in body.vertex_groups}
plates = []
for comp in isl:
    if len(comp) < 40: continue
    dom = collections.Counter()
    for vi in comp:
        best = max(me.vertices[vi].groups, key=lambda g: g.weight) if me.vertices[vi].groups else None
        if best: dom[grp_names.get(best.group, '?')] += 1
    top, cnt = dom.most_common(1)[0]
    if 'Leg' in top or 'Foot' in top:
        co = np.array([list(me.vertices[vi].co) for vi in comp]) @ MWb[:3, :3].T + MWb[:3, 3]
        plates.append({'n': len(comp), 'dom': top, 'dom_frac': cnt / len(comp),
                       'bbox': [np.round(co.min(0), 4).tolist(), np.round(co.max(0), 4).tolist()],
                       'cats': dict(dom.most_common(3))})
R['islands_total'] = len(isl); R['plate_islands'] = plates
print('[M1] islands %d  plate candidates %s' % (len(isl), [(p['n'], p['dom'], round(p['dom_frac'], 3)) for p in plates]))

# ---- rotate scene roots so glTF arms run along +-X
def wco(ob):
    m = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh() if False else ob.data
    n = len(m.vertices); co = np.empty(n * 3); m.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    MW = np.array(ob.matrix_world); return co @ MW[:3, :3].T + MW[:3, 3]
before = {o.name: wco(o) for o in (body, feet['L'], feet['R']) if o.type == 'MESH'}
Rz = Matrix.Rotation(math.radians(90.0), 4, 'Z')
RzN = np.array(Rz)
roots = [o for o in bpy.context.scene.objects if o.parent is None and o.type in ('ARMATURE', 'MESH')]
R['rotated_roots'] = [o.name for o in roots]
for o in roots: o.matrix_world = Rz @ o.matrix_world
bpy.context.view_layer.update()
after = {o.name: wco(o) for o in (body, feet['L'], feet['R']) if o.type == 'MESH'}
R['rotation_check'] = {}
for nm in before:
    exp = before[nm] @ RzN[:3, :3].T
    R['rotation_check'][nm] = float(np.max(np.abs(exp - after[nm])))
    print('[M1] rot check %-18s max|d| %.3e' % (nm, R['rotation_check'][nm]))
allw = np.vstack([after[nm] for nm in after])
R['bbox_after_rot'] = [np.round(allw.min(0), 4).tolist(), np.round(allw.max(0), 4).tolist()]
print('[M1] bbox after rot %s .. %s' % (np.round(allw.min(0), 4), np.round(allw.max(0), 4)))

bpy.ops.wm.save_as_mainfile(filepath=DST)
json.dump(R, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[M1] saved', DST)
print('[M1] DONE')
