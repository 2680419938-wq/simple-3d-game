# skin_verify.py -- measure how far apart neighbouring mesh islands drift when posed
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
SRC, OUT = a[0], a[1]
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
MESHES = [bpy.data.objects[n] for n in ('DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R')]

def world_verts():
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    out = []
    for ob in MESHES:
        ev = ob.evaluated_get(dg); me = ev.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float64); me.vertices.foreach_get('co', co)
        co = co.reshape(n, 3); M = np.array(ev.matrix_world)
        out.append(co @ M[:3, :3].T + M[:3, 3])
        ev.to_mesh_clear()
    return out

# rest positions (frame with no pose)
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
bpy.context.view_layer.update()
rest = world_verts()

# island boundary vertices + cross-island nearest pairs
pairs = []
for ob, P in zip(MESHES, rest):
    me = ob.data
    n = len(me.vertices)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for e in me.edges:
        ra, rb = find(e.vertices[0]), find(e.vertices[1])
        if ra != rb: parent[ra] = rb
    isl = np.array([find(i) for i in range(n)])
    bnd = np.zeros(n, dtype=bool)
    for e in me.edges:
        if isl[e.vertices[0]] != isl[e.vertices[1]]:
            continue
    # boundary = verts whose incident faces touch another island: approximate by verts
    # on edges where the two adjacent faces belong to different islands is unavailable for islands
    # (islands are connected components, so no such edge). Use geometric proximity instead below.
    pairs.append((ob.name, P, isl))

# geometric proximity across different islands / objects
cands = []
for i, (na, Pa, ia) in enumerate(pairs):
    for j in range(i, len(pairs)):
        nb, Pb, ib = pairs[j]
        A = Pa[::3]; B = Pb[::3]
        d2 = ((A[:, None, :] - B[None, :, :]) ** 2).sum(axis=2)
        ii, jj = np.where(d2 < 0.008 ** 2)
        for x, y in zip(ii, jj):
            va, vb = x * 3, y * 3
            if i == j and ia[va] == ib[vb]:
                continue
            cands.append((i, va, j, vb))
print('[SV] candidate seam pairs', len(cands))
if len(cands) > 4000:
    sel = np.linspace(0, len(cands) - 1, 4000).astype(int)
    cands = [cands[k] for k in sel]

def pair_dist(V):
    d = []
    for i, va, j, vb in cands:
        d.append(np.linalg.norm(V[i][va] - V[j][vb]))
    return np.array(d)

rest_d = pair_dist(rest)
POSES = [('shoulder', 'mixamorig:LeftArm', (0.3, 0.0, 0.95), 65),
         ('elbow', 'mixamorig:RightForeArm', (1.0, 0.0, 0.0), 90),
         ('hip', 'mixamorig:LeftUpLeg', (1.0, 0.0, 0.0), 50),
         ('knee', 'mixamorig:RightLeg', (1.0, 0.0, 0.0), 90),
         ('waist', 'mixamorig:Spine1', (1.0, 0.0, 0.0), 35),
         ('neck', 'mixamorig:Neck', (1.0, 0.0, 0.0), 40)]
res = {}
for name, bone, axis, ang in POSES:
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    pb = arm.pose.bones[bone]
    ax = Vector(axis).normalized()
    pb.rotation_quaternion = (Vector((0, 0, 0)).to_4d()).to_quaternion() if False else __import__('mathutils').Quaternion(ax, math.radians(ang))
    bpy.context.view_layer.update()
    V = world_verts()
    d = pair_dist(V)
    growth = d - rest_d
    res[name] = {'mean_gap_mm': round(float(growth.mean()) * 1000, 3),
                 'p95_gap_mm': round(float(np.percentile(growth, 95)) * 1000, 3),
                 'max_gap_mm': round(float(growth.max()) * 1000, 3),
                 'pairs_over_5mm': int((growth > 0.005).sum())}
    print('[SV]', name, res[name])
json.dump({'src': SRC, 'pairs': len(cands), 'poses': res,
           'rest_mean_mm': round(float(rest_d.mean()) * 1000, 3),
           'rest_max_mm': round(float(rest_d.max()) * 1000, 3)},
          open(OUT, 'w', encoding='utf-8'), indent=1)
print('[SV] wrote', OUT)
