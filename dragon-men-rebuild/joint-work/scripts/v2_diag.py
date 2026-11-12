# -*- coding: utf-8 -*-
"""Find open rims (boundary edge loops) of the ORIGINAL body verts and their relation to each joint.
Usage: blender -b --factory-startup --python v2_diag.py -- <blend> <camjson> <out.json>
"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
import jlib as JL

A = sys.argv[sys.argv.index('--') + 1:]
BLD, CAMJSON, OUT = A[0], A[1], A[2]
N0V = 21870
cams = json.load(open(CAMJSON, encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=BLD)
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data.action = None
JL.clear_pose(arm)
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
W = co @ MW[:3, :3].T + MW[:3, 3]
print('[D] verts', len(me.vertices), 'polys', len(me.polygons), flush=True)
cnt = {}
for p in me.polygons:
    vs = list(p.vertices)
    for i in range(len(vs)):
        a, b = vs[i], vs[(i + 1) % len(vs)]
        k = (a, b) if a < b else (b, a)
        cnt[k] = cnt.get(k, 0) + 1
bnd = [k for k, v in cnt.items() if v == 1]
print('[D] edges', len(cnt), 'boundary edges', len(bnd), flush=True)
adj = {}
for a, b in bnd:
    adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
seen = set(); loops = []
for s in adj:
    if s in seen:
        continue
    st = [s]; seen.add(s); comp = []
    while st:
        x = st.pop(); comp.append(x)
        for y in adj[x]:
            if y not in seen:
                seen.add(y); st.append(y)
    loops.append(comp)
loops.sort(key=len, reverse=True)
out = {'nloops': len(loops), 'loops': []}
for lp in loops:
    P = W[lp]
    c = P.mean(axis=0)
    d = {k: float(np.linalg.norm(c - np.array(cams[k]['J']))) for k in cams}
    kn = min(d, key=d.get)
    orig = sum(1 for v in lp if v < N0V)
    rec = dict(n=len(lp), orig=orig, centroid=[round(float(x), 4) for x in c],
               bbox=[round(float(x), 4) for x in P.min(axis=0)] + [round(float(x), 4) for x in P.max(axis=0)],
               nearest_joint=kn, nearest_dist=round(d[kn], 4))
    out['loops'].append(rec)
    print('[D] loop n=%-4d orig=%-4d near=%-10s d=%.4f c=%s' % (len(lp), orig, kn, d[kn], rec['centroid']), flush=True)
json.dump(out, open(OUT, 'w'), indent=1)
np.save(os.path.join(os.path.dirname(OUT), '_v2diag_loops.npy'), np.array([0]))
print('[D] DONE', OUT, flush=True)
