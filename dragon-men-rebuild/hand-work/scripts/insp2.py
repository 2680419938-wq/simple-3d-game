
# -*- coding: utf-8 -*-
"""Per-joint axial/radial profile + island structure for the four fingers (both hands). Read-only."""
import bpy, json, math
import numpy as np
from collections import defaultdict

SRC = r'D:\ai\建模\dragon-men-rebuild\std-rig\DragonMan_Std_TPose.blend'
OUT = r'D:\ai\建模\dragon-men-rebuild\hand-work\verify\insp2.json'
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']; body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
n = len(me.vertices)
co = np.empty(n * 3); me.vertices.foreach_get('co', co); P = co.reshape(n, 3) @ MW[:3, :3].T + MW[:3, 3]
MAT = [m.name for m in me.materials]
vmat = np.full(n, -1, dtype=np.int32)   # lowest material index among incident polys (Skin=2 usually dominant)
cnt = np.zeros((n, len(MAT)), dtype=np.int32)
for p in me.polygons:
    for vi in p.vertices: cnt[vi, p.material_index] += 1
vmat = cnt.argmax(1)
gname = {g.index: g.name for g in body.vertex_groups}
dom = [None] * n
for v in me.vertices:
    bw = -1; bg = None
    for ge in v.groups:
        if ge.weight > bw: bw = ge.weight; bg = gname[ge.group]
    dom[v.index] = bg
par = list(range(n))
def find(a):
    while par[a] != a:
        par[a] = par[par[a]]; a = par[a]
    return a
for e in me.edges:
    a, b = find(e.vertices[0]), find(e.vertices[1])
    if a != b: par[a] = b
root = np.array([find(i) for i in range(n)])

def bw(nm):
    b = arm.data.bones[nm]
    return np.array(arm.matrix_world @ b.head_local), np.array(arm.matrix_world @ b.tail_local)

FING = ['Thumb', 'Index', 'Middle', 'Ring']
R = {}
for side in ('Left', 'Right'):
    R[side] = {}
    for f in FING:
        joints = []
        for k in (1, 2, 3):
            h, t = bw('mixamorig:%sHand%s%d' % (side, f, k))
            joints.append((h, t))
        # finger axis frame from joint1 head -> joint3 tail
        p0 = joints[0][0]; p3 = joints[2][1]
        u = (p3 - p0) / np.linalg.norm(p3 - p0)
        tmp = np.array([0.0, 0, 1.0]) if abs(u[2]) < 0.9 else np.array([1.0, 0, 0])
        ex = np.cross(u, tmp); ex /= np.linalg.norm(ex); ey = np.cross(u, ex)
        d = P - p0
        t = d @ u
        rad = np.linalg.norm(d - np.outer(t, u), axis=1)
        Ltot = np.linalg.norm(p3 - p0)
        sel = np.where((t > -0.06) & (t < Ltot + 0.06) & (rad < 0.13))[0]
        # which islands appear in the finger cylinder
        isl = sorted(set(root[sel].tolist()))
        isl_info = []
        for r0 in isl:
            ii = np.where(root == r0)[0]
            ii = ii[np.isin(ii, sel)]
            if len(ii) == 0: continue
            isl_info.append({'root': int(r0), 'n_in_cyl': int(len(ii)),
                             't': [float(t[ii].min()), float(t[ii].max())],
                             'rho': [float(rad[ii].min()), float(rad[ii].max())],
                             'mats': {MAT[m]: int((vmat[ii] == m).sum()) for m in range(len(MAT)) if (vmat[ii] == m).any()},
                             'dom': {g: int(sum(1 for i in ii if dom[i] == g)) for g in sorted(set(dom[i] for i in ii))}})
        isl_info.sort(key=lambda x: -x['n_in_cyl'])
        # axial/rhoprofile per material for the skin-material verts
        prof = {}
        for mname in ('DragonMan_Skin', 'DragonMan_Fur', 'DragonMan_Armor'):
            mi = MAT.index(mname)
            mask = np.zeros(n, bool); mask[sel] = True; mask &= (vmat == mi)
            ii = np.where(mask)[0]
            b = {}
            nb = 24
            for k in range(nb):
                lo, hi = -0.06 + (Ltot + 0.12) * k / nb, -0.06 + (Ltot + 0.12) * (k + 1) / nb
                mm = (t[ii] >= lo) & (t[ii] < hi)
                if mm.sum() >= 2:
                    b['%.3f' % ((lo + hi) / 2)] = [int(mm.sum()), round(float(np.percentile(rad[ii][mm], 10)), 4),
                                                    round(float(np.median(rad[ii][mm])), 4), round(float(rad[ii][mm].max()), 4)]
            prof[mname] = {'n': int(len(ii)), 'bins': b}
        jt = [0.0, np.linalg.norm(joints[1][0] - joints[0][0]), np.linalg.norm(joints[2][0] - joints[0][0]), Ltot]
        print('[P] %-5s %-6s Ltot=%.4f joints_t=%s' % (side, f, Ltot, [round(x, 4) for x in jt]))
        for mname, pv in prof.items():
            if pv['n'] == 0: continue
            print('[P]    %s n=%d bins(t: n,p10,med,max): %s' % (mname[10:], pv['n'],
                  ' '.join('%s:%d/%.3f/%.3f' % (k, v[0], v[1], v[3]) for k, v in pv['bins'].items())))
        for ii in isl_info[:5]:
            print('[P]    island root=%d n=%d t=[%.3f,%.3f] rho=[%.4f,%.4f] dom=%s mats=%s' % (
                ii['root'], ii['n_in_cyl'], ii['t'][0], ii['t'][1], ii['rho'][0], ii['rho'][1], ii['dom'], ii['mats']))
        R[side][f] = {'p0': p0.tolist(), 'p3': p3.tolist(), 'Ltot': float(Ltot), 'jt': [float(x) for x in jt],
                      'islands': isl_info, 'prof': prof,
                      'joints': [[h.tolist(), tt.tolist()] for h, tt in joints]}
json.dump(R, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[P] DONE')
