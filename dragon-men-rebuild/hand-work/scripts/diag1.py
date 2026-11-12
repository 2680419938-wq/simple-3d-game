
# -*- coding: utf-8 -*-
"""Is the joint centre enclosed? Outward spheroidal ray probe + per-material first-hit distances."""
import bpy, sys, os, json, math
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\hand-work\scripts')
import numpy as np
from mathutils import Vector
import raylib as RL

SRC = r'D:\ai\建模\dragon-men-rebuild\std-rig\DragonMan_Std_TPose.blend'
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data: arm.animation_data_clear()
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('DragonMan')]
body = bpy.data.objects['DragonMan_Body']
MAT = [m.name for m in body.data.materials]

# fibonacci sphere
N = 26
dirs = []
for i in range(N):
    y = 1 - 2 * (i + 0.5) / N
    r = math.sqrt(max(0.0, 1 - y * y))
    th = math.pi * (1 + 5 ** 0.5) * i
    dirs.append(np.array([math.cos(th) * r, y, math.sin(th) * r]))

RL.clear_pose(arm)
dg = bpy.context.evaluated_depsgraph_get()
bvh = RL.world_bvh(meshes, dg)
# per-material bvh from body only
def mat_bvh(mi):
    me = body.data
    vs = list(map(tuple, [np.array(body.matrix_world @ v.co) for v in me.vertices]))
    ps = [tuple(p.vertices) for p in me.polygons if p.material_index == mi]
    return RL.BVHTree.FromPolygons(vs, ps, all_triangles=False)

MB = {m: mat_bvh(i) for i, m in enumerate(MAT)}
for side, tag, f, k, nm, par in RL.joint_list(arm):
    J = np.array(arm.matrix_world @ arm.pose.bones[nm].head)
    # nearest surface
    nloc, nnor, nidx, ndist = bvh.find_nearest(Vector(J))
    ds = []
    for d in dirs:
        loc, nor, idx, dist = bvh.ray_cast(Vector(J), Vector(d), 0.5)
        ds.append(None if loc is None else float(dist))
    got = [x for x in ds if x is not None]
    per_mat = {}
    for m, b in MB.items():
        c = 0
        for d in dirs:
            loc, nor, idx, dist = b.ray_cast(Vector(J), Vector(d), 0.5)
            if loc is not None: c += 1
        per_mat[m] = c
    print('[D] %-12s nearest=%.4f  out-hit %2d/%d  d[min,med,max]=%s  firstHitPerMat=%s'
          % ('%s %s%d' % (tag, f, k), ndist, len(got), N,
             ('%.3f/%.3f/%.3f' % (min(got), float(np.median(got)), max(got))) if got else '-', per_mat))

# cross-section of skin near L Index2 joint
J = np.array(arm.matrix_world @ arm.pose.bones['mixamorig:LeftHandIndex2'].head)
b = arm.data.bones['mixamorig:LeftHandIndex2']
bd = (np.array(arm.matrix_world @ b.tail_local) - np.array(arm.matrix_world @ b.head_local))
bd /= np.linalg.norm(bd)
me = body.data
MW = np.array(body.matrix_world)
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); P = co.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
vmat = np.zeros(len(me.vertices), np.int32) - 1
cnt = np.zeros((len(me.vertices), len(MAT)), np.int32)
for p in me.polygons:
    for vi in p.vertices: cnt[vi, p.material_index] += 1
vmat = cnt.argmax(1)
d = P - J
t = d @ bd
rad = np.linalg.norm(d - np.outer(t, bd), axis=1)
ea = np.array([0.0, 0, 1.0]) if abs(bd[2]) < 0.9 else np.array([1.0, 0, 0])
u = np.cross(bd, ea); u /= np.linalg.norm(u); v = np.cross(bd, u)
for lo, hi, lab in ((-0.010, 0.010, 'at joint'), (0.020, 0.040, 'distal 0.03'), (-0.040, -0.020, 'prox -0.03')):
    m = (t >= lo) & (t < hi) & (rad < 0.08)
    ii = np.where(m)[0]
    ang = np.degrees(np.arctan2(d[ii] @ v, d[ii] @ u))
    print('[D] L Index2 %-12s n=%d  r_p10=%.4f r_med=%.4f r_p90=%.4f  ang-bins=%s mats=%s'
          % (lab, len(ii), np.percentile(rad[ii], 10), np.median(rad[ii]), np.percentile(rad[ii], 90),
             sorted(set((ang[ii] // 30).astype(int).tolist())),
             {MAT[m2]: int((vmat[ii] == m2).sum()) for m2 in range(len(MAT)) if (vmat[ii] == m2).any()}))
print('[D] DONE')
