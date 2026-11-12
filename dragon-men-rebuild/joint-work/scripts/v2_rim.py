# -*- coding: utf-8 -*-
"""Probe: who owns the rim of the hip void at each bend? (decides where an inner lining can be anchored)
Usage: blender -b --factory-startup --python v2_rim.py -- <blend> <camjson> [KEY]
"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import jlib as JL

A = sys.argv[sys.argv.index('--') + 1:]
BLD, CAMJSON = A[0], A[1]
KEY = A[2] if len(A) > 2 else 'R_hip'
N = 320
cams = json.load(open(CAMJSON, encoding='utf-8'))
c = cams[KEY]
J = np.array(c['J'], dtype=np.float64)
bpy.ops.wm.open_mainfile(filepath=BLD)
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data.action = None
JL.clear_pose(arm)
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
W = co.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
N0V = len(me.vertices)
polys = [tuple(p.vertices) for p in me.polygons]
pmat = [(me.materials[p.material_index].name if me.materials[p.material_index] else '?') for p in me.polygons]
gidx = {g.index: g.name for g in body.vertex_groups}
dom0 = [None] * N0V
wmx = np.zeros(N0V)
for v in me.vertices:
    for g in v.groups:
        if g.weight > wmx[v.index]:
            wmx[v.index] = g.weight; dom0[v.index] = gidx[g.group]


def pdom(i):
    acc = {}
    for v in polys[i]:
        d = dom0[v]
        if d:
            acc[d] = acc.get(d, 0.0) + 1.0
    return max(acc.items(), key=lambda kv: kv[1])[0] if acc else '?'


PDOM = [pdom(i) if (pmat[i] == JL.SKIN and min(polys[i]) < N0V) else 'OTHER' for i in range(len(polys))]
trisA, ownA = [], []
for i, p in enumerate(polys):
    for k in range(1, len(p) - 1):
        trisA.append((p[0], p[k], p[k + 1])); ownA.append(i)
dv = Vector(c['front']).normalized(); cloc = Vector(J) + dv * 6.0
qq = (Vector(J) - cloc).normalized().to_track_quat('-Z', 'Y')
M4 = qq.to_matrix()
rgt = np.array(M4.col[0], dtype=np.float64); upp = np.array(M4.col[1], dtype=np.float64)
fw = -np.array(M4.col[2], dtype=np.float64)
sca = float(c['scale_front'])
for bend in (0.0, 90.0):
    JL.clear_pose(arm)
    JL.set_rot(arm, 'mixamorig:RightUpLeg', np.array(c['a1']), bend)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    obe = body.evaluated_get(dg)
    m2 = obe.to_mesh()
    V = np.empty(len(m2.vertices) * 3); m2.vertices.foreach_get('co', V)
    V = V.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
    obe.to_mesh_clear()
    bvh = BVHTree.FromPolygons([tuple(x) for x in V], trisA, all_triangles=True)
    OWN = -np.ones((N, N), np.int64); VOID = np.zeros((N, N), bool); DEP = np.zeros((N, N))
    for py in range(N):
        for px in range(N):
            o = np.array(cloc) + rgt * (((px + 0.5) / N - 0.5) * sca) + upp * (((py + 0.5) / N - 0.5) * sca) - fw * 6.0
            h = bvh.ray_cast(Vector(o), Vector(fw), 12.0)
            if h[0] is None:
                s = float(fw @ (J - np.array(o)))
                if float(np.linalg.norm(np.array(o) + s * fw - J)) < 0.052:
                    VOID[py, px] = True
            else:
                OWN[py, px] = ownA[h[2]]
                DEP[py, px] = float((np.array(h[0]) - o) @ fw)
    hist = {}
    dep = []
    for py, px in zip(*np.nonzero(VOID)):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = py + dy, px + dx
                if 0 <= ny < N and 0 <= nx < N and OWN[ny, nx] >= 0:
                    nm = PDOM[OWN[ny, nx]]
                    hist[nm] = hist.get(nm, 0) + 1
                    dep.append(DEP[ny, nx])
    print('[R] bend%-3d void=%d  rim owners: %s' % (int(bend), int(VOID.sum()),
          sorted(hist.items(), key=lambda kv: -kv[1])[:8]), flush=True)
    if dep:
        print('[R]   rim depth p10/med/p90 %.3f %.3f %.3f  (cam plane at 12.0)' % tuple(np.percentile(dep, [10, 50, 90])), flush=True)
JL.clear_pose(arm)
print('[R] DONE', flush=True)
