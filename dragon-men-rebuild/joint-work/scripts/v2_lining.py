# -*- coding: utf-8 -*-
"""TASK A: recessed skin lining inside the hip gap, appended as a new block to DragonMan_Body.
Rest-pose screen-space sheet, fitted to the PELVIS-side rim of the void (so it stays visible when the
thigh swings away): crack = background rays passing near J; region = void pixels within DS px of a
non-thigh skin rim; depth = that rim's depth + recess bowl -> always behind the existing skin surface.
Usage: blender -b --factory-startup --python v2_lining.py -- <inblend> <outblend> <camjson> <outjson>
       [KEY=R_hip] [target_frac=0.0050] [recess=0.006] [nearJ=0.052] [mode=build|probe]
"""
import bpy, bmesh, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from collections import deque
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import jlib as JL

A = sys.argv[sys.argv.index('--') + 1:]
INB, OUTB, CAMJSON, OUTJ = A[0], A[1], A[2], A[3]
KEY = A[4] if len(A) > 4 else 'R_hip'
TFRAC = float(A[5]) if len(A) > 5 else 0.0050
RECESS = float(A[6]) if len(A) > 6 else 0.006
NEARJ = float(A[7]) if len(A) > 7 else 0.052
MODE = A[8] if len(A) > 8 else 'build'
N = 320
SKIN = JL.SKIN
SOCKMIN = 22814
PDd = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'renders', 'v2', 'probe')
os.makedirs(PDd, exist_ok=True)

cams = json.load(open(CAMJSON, encoding='utf-8'))
c = cams[KEY]
J = np.array(c['J'], dtype=np.float64)
BR = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'verify', 'build_report.json'), encoding='utf-8'))
JD = [j for j in BR['joints'] if j['key'] == KEY][0]
MED = float(JD['med'])
CHILD, PAR = JD['bone'], JD['par']

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
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
W = co.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
N0V = len(me.vertices); N0P = len(me.polygons)
polys = [tuple(p.vertices) for p in me.polygons]
pmat = [(me.materials[p.material_index].name if me.materials[p.material_index] else '?') for p in me.polygons]
skin_i = [m.name for m in me.materials].index(SKIN)
print('[L] verts', N0V, 'polys', N0P, 'skin_i', skin_i, flush=True)

# ---- vertex group tables ----
gidx = {g.index: g.name for g in body.vertex_groups}
vgr = [dict((gidx[g.group], g.weight) for g in v.groups) for v in me.vertices]
have = set(gidx.values())
dom0 = [None] * N0V
wmx = np.zeros(N0V)
for v in me.vertices:
    for g in v.groups:
        if g.weight > wmx[v.index]:
            wmx[v.index] = g.weight; dom0[v.index] = gidx[g.group]
vskin = np.ones(N0V, bool)
for i, p in enumerate(polys):
    if pmat[i] != SKIN:
        for v in p:
            if v < N0V:
                vskin[v] = False


def pdom(i):
    acc = {}
    for v in polys[i]:
        d = dom0[v]
        if d:
            acc[d] = acc.get(d, 0.0) + wmx[v] + 1e-6
    return max(acc.items(), key=lambda kv: kv[1])[0] if acc else None


trisA, ownA, trisS, ownS, trisC, ownC, trisP, ownP = [], [], [], [], [], [], [], []
for i, p in enumerate(polys):
    for k in range(1, len(p) - 1):
        t = (p[0], p[k], p[k + 1])
        trisA.append(t); ownA.append(i)
    if pmat[i] != SKIN or min(p) >= N0V:
        continue
    d = pdom(i)
    for k in range(1, len(p) - 1):
        t = (p[0], p[k], p[k + 1])
        trisS.append(t); ownS.append(i)
        if d == CHILD:
            trisC.append(t); ownC.append(i)
        else:
            trisP.append(t); ownP.append(i)
PDOM = [pdom(i) if (pmat[i] == SKIN and min(polys[i]) < N0V) else None for i in range(len(polys))]
vA = [tuple(x) for x in W]
bvhAll = BVHTree.FromPolygons(vA, trisA, all_triangles=True)
bvhSkin = BVHTree.FromPolygons(vA, trisS, all_triangles=True)
bvhC = BVHTree.FromPolygons(vA, trisC, all_triangles=True)
bvhP = BVHTree.FromPolygons(vA, trisP, all_triangles=True)
print('[L] tris all %d skin-orig %d child %d parent %d' % (len(trisA), len(trisS), len(trisC), len(trisP)), flush=True)

# ---- camera basis (same as hip_gapcheck / j3_render) ----
loc = Vector(J) + Vector(c['front']).normalized() * 6.0
q = (Vector(J) - loc).normalized().to_track_quat('-Z', 'Y')
M3 = q.to_matrix()
right = np.array(M3.col[0], dtype=np.float64); up = np.array(M3.col[1], dtype=np.float64)
fwd = -np.array(M3.col[2], dtype=np.float64)
SC = float(c['scale_front'])
CENT = np.array(loc, dtype=np.float64)


def origin(px, py):
    return CENT + right * (((px + 0.5) / N - 0.5) * SC) + up * (((py + 0.5) / N - 0.5) * SC) - fwd * 6.0


def perp_J(o):
    s = float(fwd @ (J - o))
    return float(np.linalg.norm(o + s * fwd - J))


# ---- ray pass: background / first hit point / owner poly ----
HITP = np.zeros((N, N, 3))
HITM = np.zeros((N, N), bool)
BG = np.zeros((N, N), bool)
OWN = -np.ones((N, N), np.int64)
for py in range(N):
    for px in range(N):
        o = origin(px, py)
        h = bvhAll.ray_cast(Vector(o), Vector(fwd), 12.0)
        if h[0] is None:
            BG[py, px] = True
        else:
            HITM[py, px] = True
            HITP[py, px] = np.array(h[0], dtype=np.float64)
            OWN[py, px] = ownA[h[2]]
print('[L] bg px', int(BG.sum()), 'hit px', int(HITM.sum()), flush=True)
CRK = np.zeros((N, N), bool)
for py, px in zip(*np.nonzero(BG)):
    if perp_J(origin(int(px), int(py))) < NEARJ:
        CRK[py, px] = True
print('[L] crack px', int(CRK.sum()), flush=True)
PELV = np.zeros((N, N), bool)
for py, px in zip(*np.nonzero(HITM)):
    d = PDOM[OWN[py, px]] if OWN[py, px] >= 0 else None
    if d is not None and d != CHILD:
        PELV[py, px] = True
print('[L] pelvis-side rim px', int(PELV.sum()), 'thigh-side rim px', int((HITM & ~PELV).sum()), flush=True)


def bfs(src_mask):
    INF = 1e9
    D = np.full((N, N), INF)
    S = np.full((N, N, 2), -1, np.int32)
    dq = deque()
    for y, x in zip(*np.nonzero(src_mask)):
        D[y, x] = 0.0; S[y, x] = (y, x); dq.append((int(y), int(x)))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < N and 0 <= nx < N and D[ny, nx] > D[y, x] + 1.0:
                D[ny, nx] = D[y, x] + 1.0; S[ny, nx] = S[y, x]; dq.append((ny, nx))
    return D, S


def label(mask):
    NY, NX = mask.shape
    lab = -np.ones(mask.shape, np.int32); cur = 0; sizes = []
    for y, x in zip(*np.nonzero(mask)):
        if lab[y, x] >= 0:
            continue
        st = [(y, x)]; lab[y, x] = cur; n = 0
        while st:
            cy, cx = st.pop(); n += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < NY and 0 <= nx < NX and mask[ny, nx] and lab[ny, nx] < 0:
                    lab[ny, nx] = cur; st.append((ny, nx))
        sizes.append(n); cur += 1
    return lab, sizes


DIST, SRC = bfs(PELV)
TARGET = TFRAC * N * N
best = None
for ds in range(1, 26):
    m = CRK & (DIST <= ds)
    lab, sizes = label(m)
    if not sizes:
        continue
    big = int(np.argmax(sizes)); sz = sizes[big]
    if best is None or abs(sz - TARGET) < abs(best[0] - TARGET):
        best = (sz, ds, big, lab)
sz, DS, BLAB, LAB = best
SEL = CRK & (DIST <= DS) & (LAB == BLAB)
lab, sizes = label(SEL)
SEL = (lab == int(np.argmax(sizes)))
print('[L] rim-band DS %d px core %d (%.3f%% of frame, target %.0f)' % (DS, int(SEL.sum()), 100.0 * SEL.sum() / (N * N), TARGET), flush=True)
sel_px = [(int(x), int(y)) for y, x in zip(*np.nonzero(SEL))]
PIDX = -np.ones((N, N), np.int64)
for i, (x, y) in enumerate(sel_px):
    PIDX[y, x] = i

# ---- depth field: pelvis-rim depth + recess bowl, smoothed ----
S = np.zeros((N, N)); DV = np.zeros((N, N))
for (x, y) in sel_px:
    sy, sx = [int(t) for t in SRC[y, x]]
    if sy < 0:
        DV[y, x] = 0.0008; continue
    S[y, x] = float(fwd @ (HITP[sy, sx] - origin(x, y)))
    r = DIST[y, x]
    sh = min(1.0, r / 3.0)
    sh = sh * sh * (3 - 2 * sh)
    DV[y, x] = 0.0008 if r <= 1.0 else 0.0008 + (RECESS - 0.0008) * sh
for _ in range(6):
    S2 = S.copy()
    for (x, y) in sel_px:
        acc = 0.0; n = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < N and 0 <= nx < N and SEL[ny, nx]:
                    acc += S[ny, nx]; n += 1
        S2[y, x] = acc / n
    S = S2
VW = np.zeros((len(sel_px), 3))
for i, (x, y) in enumerate(sel_px):
    VW[i] = origin(x, y) + (S[y, x] + DV[y, x]) * fwd
print('[L] verts %d depth med %.4f recess max %.4f' % (len(sel_px), float(np.median(S[SEL])), DV[SEL].max()), flush=True)

if MODE == 'probe':
    img = np.zeros((N, N, 4), np.float32); img[..., 3] = 1.0
    img[..., 0] = 0.12; img[..., 1] = 0.42; img[..., 2] = 0.12
    img[HITM] = (0.30, 0.30, 0.42, 1.0)
    img[PELV] = (0.75, 0.75, 0.95, 1.0)
    img[CRK] = (0.95, 0.10, 0.10, 1.0)
    img[SEL] = (0.10, 0.85, 0.95, 1.0)
    im = bpy.data.images.new('sel', N, N)
    im.pixels.foreach_set(img[::-1].ravel())
    im.filepath_raw = os.path.join(PDd, 'selmask_%s_rest_front.png' % KEY); im.file_format = 'PNG'; im.save()
    print('[L] probe done', flush=True)
    bpy.ops.wm.quit_blender()
    sys.exit(0)

# ---- faces ----
faces = []
for (x, y) in sel_px:
    a = PIDX[y, x]
    b = PIDX[y, x + 1] if x + 1 < N else -1
    cc_ = PIDX[y + 1, x + 1] if (x + 1 < N and y + 1 < N) else -1
    d = PIDX[y + 1, x] if y + 1 < N else -1
    if b >= 0 and cc_ >= 0 and d >= 0:
        faces.append((a, b, cc_, d))
    else:
        if b >= 0 and cc_ >= 0:
            faces.append((a, b, cc_))
        if cc_ >= 0 and d >= 0:
            faces.append((a, cc_, d))
        if b >= 0 and d >= 0 and cc_ < 0:
            faces.append((a, b, d))
print('[L] faces', len(faces), flush=True)


def bary(p, a, b, cc_):
    v0 = b - a; v1 = cc_ - a; v2 = p - a
    d00 = v0 @ v0; d01 = v0 @ v1; d11 = v1 @ v1; d20 = v2 @ v0; d21 = v2 @ v1
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-16:
        return np.array([1.0, 0.0, 0.0])
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return np.array([1.0 - v - w, v, w])


def wt_of(ti):
    p = polys[ownS[ti]]
    bw = bary(np.array(ti[0:0] + ()) if False else np.array(PNT[ti]), W[p[0]], W[p[1]], W[p[2]])
    acc = {}
    for k in range(3):
        for bn, wt in vgr[p[k]].items():
            acc[bn] = acc.get(bn, 0.0) + bw[k] * wt
    return acc


PNT = [None] * len(trisS)
for i in range(len(trisS)):
    PNT[i] = (0.0, 0.0, 0.0)
NEWW = []; domn = []
for i in range(len(VW)):
    lc, nc, tc, dcv = bvhC.find_nearest(Vector(VW[i]))
    lp, np_, tp, dpv = bvhP.find_nearest(Vector(VW[i]))
    PNT[tc] = tuple(lc); PNT[tp] = tuple(lp)
    ac_ = wt_of(tc); ap = wt_of(tp)
    tot = max(1e-9, dcv + dpv)
    wc = dpv / tot; wp = dcv / tot
    acc = {}
    for bn, wt in ac_.items():
        acc[bn] = acc.get(bn, 0.0) + wc * wt
    for bn, wt in ap.items():
        acc[bn] = acc.get(bn, 0.0) + wp * wt
    acc = dict(sorted(acc.items(), key=lambda kv: -kv[1])[:4])
    s = sum(acc.values())
    acc = {k: v / s for k, v in acc.items() if v / s >= 0.005}
    s = sum(acc.values())
    acc = {k: v / s for k, v in acc.items()}
    miss = set(acc) - have
    assert not miss, 'vertex group missing: %s' % miss
    NEWW.append(acc); domn.append(max(acc.items(), key=lambda kv: kv[1])[0])
doms = {}
for d in domn:
    doms[d] = doms.get(d, 0) + 1
print('[L] dominant groups', doms, flush=True)
print('[L] influences min/max', min(len(w) for w in NEWW), max(len(w) for w in NEWW), flush=True)
print('[L] w(child) min/med/max %.3f %.3f %.3f' % (min(w.get(CHILD, 0.0) for w in NEWW),
      float(np.median([w.get(CHILD, 0.0) for w in NEWW])), max(w.get(CHILD, 0.0) for w in NEWW)), flush=True)

# ---- UV: MLS affine transfer on map1 (uv_fix.py math) ----
uvm = np.zeros(len(me.loops) * 2)
me.uv_layers['map1'].data.foreach_get('uv', uvm)
uvm = uvm.reshape(-1, 2)
pd = np.zeros((N0V, 2)); seen = np.zeros(N0V, bool)
for li, lp in enumerate(me.loops):
    vi = lp.vertex_index
    if vi < N0V and not seen[vi]:
        pd[vi] = uvm[li]; seen[vi] = True
roots = (CHILD, PAR)


def okbone(i):
    d = dom0[i]
    if d is None:
        return False
    return d in roots or any(d.startswith(r.rsplit(':', 1)[-1]) or r.endswith(d.rsplit(':', 1)[-1]) for r in roots)


R = max(0.06, 1.5 * MED)
cand = []
for rr in (R, 2 * R, 4 * R, 8 * R):
    cand = [i for i in range(N0V) if vskin[i] and okbone(i) and np.linalg.norm(W[i] - J) < rr]
    if len(cand) >= 8:
        break
C = np.array(cand, dtype=np.int64)
DU = pd[C]; D = W[C] - J
print('[L] uv donors', len(C), 'R', round(R, 4), flush=True)
NEWUV = np.zeros((len(VW), 2))
for i in range(len(VW)):
    d = np.linalg.norm(D - (VW[i] - J), axis=1)
    k = np.argsort(d)[:40]
    dk = d[k]
    wgt = np.exp(-(dk / max(1e-4, MED)) ** 2) + 1e-6
    X = np.hstack([np.ones((len(k), 1)), D[k]])
    y = DU[k]

    def fit(wg):
        Xw = X * wg[:, None]
        sol, *_ = np.linalg.lstsq(Xw.T @ X, Xw.T @ y, rcond=None)
        return sol
    sol = fit(wgt)
    rres = np.linalg.norm(y - X @ sol, axis=1)
    keep = rres <= max(2.5 * np.median(rres), 1e-6)
    if keep.sum() >= 6:
        sol = fit(wgt * keep)
    NEWUV[i] = sol[0] + sol[1:].T @ (VW[i] - J)

# ---- append geometry ----
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
nv = []
for i in range(len(VW)):
    q4 = MWi @ Vector((VW[i][0], VW[i][1], VW[i][2], 1.0))
    nv.append(bm.verts.new(Vector((q4[0], q4[1], q4[2]))))
bm.verts.index_update()
nf = 0
for f in faces:
    try:
        fc = bm.faces.new([nv[i] for i in f])
    except ValueError:
        continue
    fc.smooth = True
    fc.material_index = skin_i
    nf += 1
bm.to_mesh(me)
bm.free()
me.update()
print('[L] mesh now verts', len(me.vertices), 'polys', len(me.polygons), 'new faces', nf, flush=True)
assert len(me.vertices) == N0V + len(VW)
for i in range(len(VW)):
    vi = N0V + i
    for bn, wt in NEWW[i].items():
        body.vertex_groups.get(bn).add([vi], float(wt), 'REPLACE')
nl = 0
for i in range(N0P, len(me.polygons)):
    p = me.polygons[i]
    for k in range(len(p.vertices)):
        li = p.loop_start + k
        vi = me.loops[li].vertex_index
        if vi >= N0V:
            me.uv_layers['map1'].data[li].uv = Vector((float(NEWUV[vi - N0V][0]), float(NEWUV[vi - N0V][1])))
            nl += 1
print('[L] map1 loops written', nl, flush=True)

# ---- counterfactual coverage (hip_gapcheck rule: min(poly) >= 22814) ----
polysA = [tuple(p.vertices) for p in me.polygons]
is_sock = [min(p) >= SOCKMIN for p in polysA]
COV = {}
for bend in (0.0, 60.0, 90.0):
    JL.clear_pose(arm)
    JL.set_rot(arm, CHILD, np.array(c['a1']), bend)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    obe = body.evaluated_get(dg)
    m2 = obe.to_mesh()
    V = np.empty(len(m2.vertices) * 3); m2.vertices.foreach_get('co', V)
    V = V.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
    obe.to_mesh_clear()
    tA = []; oA = []; tB = []
    for i, p in enumerate(polysA):
        for k in range(1, len(p) - 1):
            tA.append((p[0], p[k], p[k + 1])); oA.append(i)
            if not is_sock[i]:
                tB.append((p[0], p[k], p[k + 1]))
    vv = [tuple(x) for x in V]
    bA = BVHTree.FromPolygons(vv, tA, all_triangles=True)
    bB = BVHTree.FromPolygons(vv, tB, all_triangles=True)
    COV['bend%d' % int(bend)] = {}
    for suf in ('front', 'side'):
        sca = float(c['scale_' + suf]); dv_ = Vector(c[suf]).normalized()
        cloc = Vector(J) + dv_ * 6.0
        qq = (Vector(J) - cloc).normalized().to_track_quat('-Z', 'Y')
        M4 = qq.to_matrix()
        rgt = np.array(M4.col[0], dtype=np.float64); upp = np.array(M4.col[1], dtype=np.float64)
        fw2 = -np.array(M4.col[2], dtype=np.float64)
        op = 0; bgw = 0; sockv = 0; mine = 0
        for py in range(N):
            for px in range(N):
                o = np.array(cloc) + rgt * (((px + 0.5) / N - 0.5) * sca) + upp * (((py + 0.5) / N - 0.5) * sca) - fw2 * 6.0
                ha = bA.ray_cast(Vector(o), Vector(fw2), 12.0)
                if ha[0] is None:
                    bgw += 1
                else:
                    if min(polysA[oA[ha[2]]]) >= N0V:
                        mine += 1
                    if is_sock[oA[ha[2]]]:
                        sockv += 1
                        hb = bB.ray_cast(Vector(o), Vector(fw2), 12.0)
                        if hb[0] is None:
                            op += 1
        COV['bend%d' % int(bend)][suf] = dict(opened=op, pc=round(100.0 * op / (N * N), 3), bg=bgw, sock=sockv, new_first=mine)
        print('[L] COV %-5s %-5s opened=%d (%.3f%%) bg=%d sock=%d new_first=%d'
              % ('bend%d' % int(bend), suf, op, 100.0 * op / (N * N), bgw, sockv, mine), flush=True)

JL.clear_pose(arm)
if ACT is not None:
    try:
        arm.animation_data.action = ACT
        arm.animation_data.action_slot = ACT.slots[0]
    except Exception as e:
        print('[B] slot warn', e, flush=True)
bpy.context.view_layer.update()
rep = dict(key=KEY, N0V=N0V, nverts_new=len(VW), nfaces_new=nf, sel_px=int(SEL.sum()), target_px=round(TARGET, 1),
           ds_px=int(DS), recess=RECESS, nearJ=NEARJ, depth_med=round(float(np.median(S[SEL])), 5),
           dominant=doms, cover=COV, blend=OUTB)
json.dump(rep, open(OUTJ, 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[L] DONE', OUTB, flush=True)
