# -*- coding: utf-8 -*-
"""v2_gap_probe: find the open boundaries of DragonMan_Body near the two hip joints.
Reports every boundary loop: vert count, centroid, bbox, distance to each joint J,
adjacent-face material tally, closed-or-not.
Usage: blender -b --factory-startup --python v2_gap_probe.py -- <blend> <out.json>
"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
import jlib as J

A = sys.argv[sys.argv.index('--') + 1:]
BLD, OUT = A[0], A[1]
BR = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'verify', 'build_report.json'), encoding='utf-8'))
N0V = 21870

bpy.ops.wm.open_mainfile(filepath=BLD)
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
W = co @ MW[:3, :3].T + MW[:3, 3]
NV, NP = len(me.vertices), len(me.polygons)
print('[P] verts %d polys %d (orig %d)' % (NV, NP, N0V), flush=True)

# edge -> face count
ecount = {}
for p in me.polygons:
    vs = list(p.vertices)
    for k in range(len(vs)):
        e = (min(vs[k], vs[(k + 1) % len(vs)]), max(vs[k], vs[(k + 1) % len(vs)]))
        ecount[e] = ecount.get(e, 0) + 1
bnd = [e for e, c in ecount.items() if c == 1]
print('[P] edges %d boundary %d' % (len(ecount), len(bnd)), flush=True)

# adjacency over boundary edges
adj = {}
for a, b in bnd:
    adj.setdefault(a, set()).add(b)
    adj.setdefault(b, set()).add(a)
seen = set()
comps = []
for v in adj:
    if v in seen:
        continue
    stack = [v]; comp = []
    seen.add(v)
    while stack:
        x = stack.pop(); comp.append(x)
        for y in adj[x]:
            if y not in seen:
                seen.add(y); stack.append(y)
    comps.append(sorted(comp))
comps.sort(key=len, reverse=True)

mats = [m.name if m else '?' for m in me.materials]
pmat = [mats[p.material_index] for p in me.polygons]
Jkeys = {j['key']: np.array(j['J']) for j in BR['joints']}

rep = dict(blend=BLD, nverts=NV, npolys=NP, nedges=len(ecount), nbnd_edges=len(bnd),
           ncomp=len(comps), comps=[])
for ci, comp in enumerate(comps[:20]):
    P = W[comp]
    c = P.mean(0)
    dist = {k: float(np.min(np.linalg.norm(P - Jv, axis=1))) for k, Jv in Jkeys.items()}
    near = sorted(dist.items(), key=lambda kv: kv[1])[:3]
    # adjacent faces: those touching a boundary vert
    vs = set(comp)
    tally = {}
    for i, p in enumerate(me.polygons):
        if any(int(v) in vs for v in p.vertices):
            tally[pmat[i]] = tally.get(pmat[i], 0) + 1
    # loop closed?
    open_end = sum(1 for v in comp if len(adj[v]) == 1)
    rep['comps'].append(dict(i=ci, nv=len(comp), nopen_end=open_end,
                             c=[round(float(x), 4) for x in c],
                             bbox_min=[round(float(x), 4) for x in P.min(0)],
                             bbox_max=[round(float(x), 4) for x in P.max(0)],
                             ext=[round(float(x), 4) for x in (P.max(0) - P.min(0))],
                             nearest=near, vmin=int(min(comp)), vmax=int(max(comp)),
                             all_orig=bool(max(comp) < N0V), mats=tally))
    print('[P] comp %2d nv=%4d open_end=%d ext=%s nearest=%s mats=%s' % (
        ci, len(comp), open_end, rep['comps'][-1]['ext'],
        [(k, round(d, 4)) for k, d in near], tally), flush=True)

json.dump(rep, open(OUT, 'w'), indent=1)
print('[P] DONE', OUT, flush=True)
