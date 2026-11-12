
# -*- coding: utf-8 -*-
"""j10 v2: hip socket vs skin — skin-only radial profile at J, per-vertex signed
containment, and where the current socket pokes out."""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = r'D:\ai\建模\dragon-men-rebuild\joint-work'
BLD = os.path.join(OUT, 'DragonMan_Joint_full.blend')
BR = json.load(open(os.path.join(OUT, 'verify', 'build_report.json')))

bpy.ops.wm.open_mainfile(filepath=BLD)
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)
bpy.context.view_layer.update()
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
PW = co @ MW[:3, :3].T + MW[:3, 3]
V = [tuple(v) for v in PW]
recs = {j['key']: j for j in BR['joints']}
GA = math.pi * (3 - math.sqrt(5))

def fib(n):
    out = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(max(0.0, 1 - z * z)); th = GA * i
        out.append(Vector((r * math.cos(th), r * math.sin(th), z)))
    return out

for key in ('R_hip', 'L_hip'):
    jd = recs[key]
    b, n = jd['base'], jd['nvp']
    J = Vector(jd['J'])
    sf = [tuple(p.vertices) for p in me.polygons if all(b <= v < b + n for v in p.vertices)]
    of = [tuple(p.vertices) for p in me.polygons if not all(b <= v < b + n for v in p.vertices)]
    skin = BVHTree.FromPolygons(V, of, all_triangles=False)
    print('  [D] === %s  J=%s  SOCK=%s ===' % (key, np.round(np.array(J), 5), jd['sock']['R']))
    ds = []
    openn = []
    for d in fib(128):
        h = skin.ray_cast(J, d, 0.6)
        if h[0] is None:
            openn.append(d)
        else:
            ds.append(h[3])
    print('  [D] skin-only radial 128: min %.5f  p10 %.5f  med %.5f  max %.5f  open %d' % (
        min(ds), float(np.percentile(ds, 10)), float(np.median(ds)), max(ds), len(openn)))
    # smallest-lobe directions
    order = np.argsort(np.array(ds))
    dd = fib(128)
    small = [(np.round(np.array(dd[i]), 3), round(ds[i], 5)) for i in order[:6]]
    print('  [D] thinnest dirs:', small)
    print('  [D] mean dir', np.round(np.mean(PW[b:b + n], axis=0), 4), ' centroid-J', np.round(np.mean(PW[b:b + n], axis=0) - np.array(J), 5))
    # per-vertex: radial dist from J vs skin dist along that direction
    S = PW[b:b + n]
    rel = S - np.array(J)
    dot = (rel * rel).sum(axis=1)
    outs = []
    nearmiss = 0
    for i in range(n):
        r = float(np.linalg.norm(rel[i]))
        if r < 1e-9:
            continue
        h = skin.ray_cast(J, Vector(rel[i] / r), 0.6)
        sd = h[3] if h[0] is not None else None
        if sd is None or sd < r - 1e-6:
            outs.append((i, r, sd))
    print('  [D] socket verts %d ; poke-out-of-skin verts %d' % (n, len(outs)))
    if outs:
        print('  [D] poke depth max %.5f  mean %.5f' % (max(o[1] - (o[2] or 0) for o in outs),
              float(np.mean([o[1] - (o[2] or 0) for o in outs]))))
        far = sorted(outs, key=lambda o: -(o[1] - (o[2] or 0)))[:5]
        print('  [D] worst verts (idx, r, skinDist, depth):', [(o[0], round(o[1], 4), None if o[2] is None else round(o[2], 4), round(o[1] - (o[2] or 0), 4)) for o in far])
    # nearest-point signed test (normal side)
    nout = 0; dmax = 0.0
    for i in range(n):
        p = Vector(S[i])
        loc, nor, idx, dist = skin.find_nearest(p)
        if loc is None:
            continue
        sgn = float((p - loc).dot(nor))
        if sgn > 0:
            nout += 1
            dmax = max(dmax, sgn)
    print('  [D] nearest-point test: verts outside skin surface %d / %d ; max outside %.5f' % (nout, n, dmax))
print('  [D] DONE')
