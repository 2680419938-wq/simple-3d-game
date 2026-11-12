
# -*- coding: utf-8 -*-
"""Read-only inspection of the std T-pose blend: objects, materials, UV, finger bones, joint topology."""
import bpy, json, math
import numpy as np
from collections import defaultdict

SRC = r'D:\ai\建模\dragon-men-rebuild\std-rig\DragonMan_Std_TPose.blend'
OUT = r'D:\ai\建模\dragon-men-rebuild\hand-work\verify\insp1.json'
bpy.ops.wm.open_mainfile(filepath=SRC)
R = {}
print('[I] objects:', [(o.name, o.type) for o in bpy.data.objects])
R['objects'] = [(o.name, o.type, len(o.data.vertices) if o.type == 'MESH' else 0) for o in bpy.data.objects]
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
print('[I] armature', arm.name, 'bones', len(arm.data.bones), 'scale', tuple(arm.scale), 'world', [list(r) for r in arm.matrix_world])
R['arm'] = {'name': arm.name, 'nbones': len(arm.data.bones), 'scale': list(arm.scale),
            'matrix_world': [list(r) for r in arm.matrix_world],
            'actions': [a.name for a in bpy.data.actions],
            'has_anim': bool(arm.animation_data and arm.animation_data.action)}
def nfcurves(act):
    try:
        return len(act.fcurves)
    except Exception:
        c = 0
        for lay in getattr(act, 'layers', []):
            for st in lay.strips:
                for cb in getattr(st, 'channelbags', []):
                    c += len(cb.fcurves)
        return c
if arm.animation_data and arm.animation_data.action:
    R['arm']['action'] = arm.animation_data.action.name
    R['arm']['n_fcurves'] = nfcurves(arm.animation_data.action)
R['arm']['action_fcurves'] = {a.name: nfcurves(a) for a in bpy.data.actions}
print('[I] actions', [a.name for a in bpy.data.actions], 'anim', R['arm'].get('action'), R['arm'].get('n_fcurves'))

AW = np.array(arm.matrix_world)
def bone_w(nm):
    b = arm.data.bones[nm]
    h = np.array(arm.matrix_world @ b.head_local)
    t = np.array(arm.matrix_world @ b.tail_local)
    return h, t, (h + t) * 0.5
print('[I] deform bones:', sum(1 for b in arm.data.bones if b.use_deform), 'of', len(arm.data.bones))
print('[I] non-deform:', [b.name for b in arm.data.bones if not b.use_deform])

FING = ['Thumb', 'Index', 'Middle', 'Ring']
BT = {}
for s, side in (('L', 'Left'), ('R', 'Right')):
    BT[side] = {'Hand': None, 'f': {}}
    for f in FING:
        ch = []
        for k in (1, 2, 3):
            h, t, m = bone_w('mixamorig:%sHand%s%d' % (side, f, k))
            ch.append((h, t))
        BT[side]['f'][f] = ch
        print('[I] %-5s %-6s ' % (side, f) + ' | '.join('h=%s L=%.4f' % (np.round(h, 3), np.linalg.norm(t - h)) for h, t in ch))
    h, t, m = bone_w('mixamorig:%sHand' % side)
    BT[side]['Hand'] = (h, t)
    print('[I] %-5s Hand head=%s tail=%s' % (side, np.round(h, 3), np.round(t, 3)))
R['bones'] = {side: {'Hand': [BT[side]['Hand'][0].tolist(), BT[side]['Hand'][1].tolist()],
                     'f': {f: [[a.tolist(), b.tolist()] for a, b in BT[side]['f'][f]] for f in FING}}
               for side in BT}

body = bpy.data.objects['DragonMan_Body']
me = body.data
print('[I] body verts', len(me.vertices), 'polys', len(me.polygons), 'tris',
      len(me.polygons) + sum(1 for p in me.polygons if len(p.vertices) == 4))
print('[I] materials', [(i, m.name if m else None) for i, m in enumerate(me.materials)])
print('[I] uv layers', [(u.name, u.active_render) for u in me.uv_layers])
print('[I] vertex groups', len(body.vertex_groups))
R['body'] = {'verts': len(me.vertices), 'polys': len(me.polygons),
             'materials': [m.name if m else None for m in me.materials],
             'uv': [u.name for u in me.uv_layers],
             'modifiers': [(m.type, m.name, getattr(m, 'object', None).name if getattr(m, 'object', None) else None) for m in body.modifiers],
             'vgroups': [g.name for g in body.vertex_groups]}
print('[I] modifiers', R['body']['modifiers'])

MW = np.array(body.matrix_world)
n = len(me.vertices)
co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(n, 3)
P = co @ MW[:3, :3].T + MW[:3, 3]
gname = {g.index: g.name for g in body.vertex_groups}
dom = [None] * n; wmax = np.zeros(n); ngrp = np.zeros(n, dtype=int)
for v in me.vertices:
    bw = -1.0; bg = None; c = 0
    for ge in v.groups:
        if ge.weight > 1e-9: c += 1
        if ge.weight > bw: bw = ge.weight; bg = gname[ge.group]
    dom[v.index] = bg; wmax[v.index] = bw; ngrp[v.index] = c
print('[I] weight purity on body: verts with dominant weight >0.999: %d / %d ; mean influences %.2f'
      % (int((wmax > 0.999).sum()), n, ngrp.mean()))

# material index per vertex (from polygons)
mat_of_vert = defaultdict(set)
for p in me.polygons:
    for vi in p.vertices: mat_of_vert[vi].add(p.material_index)
matnames = [m.name if m else None for m in me.materials]

# hand region: verts dominated by Left/RightHand* bones
REP = {}
for side in ('Left', 'Right'):
    pref = 'mixamorig:%sHand' % side
    sel = [i for i in range(n) if dom[i] and dom[i].startswith(pref)]
    print('[I] %-5s hand-bone dominant verts: %d' % (side, len(sel)))
    mats = defaultdict(int)
    for i in sel:
        for mi in mat_of_vert[i]: mats[matnames[mi]] += 1
    print('[I]   materials over those verts:', dict(mats))
    REP[side] = {'n': len(sel), 'mats': dict(mats)}
    for f in FING:
        per = {}
        for k in (1, 2, 3):
            bn = 'mixamorig:%sHand%s%d' % (side, f, k)
            ids = [i for i in sel if dom[i] == bn]
            if ids:
                r0 = np.linalg.norm(P[ids] - BT[side]['f'][f][k - 1][0], axis=1)
                per[k] = {'n': len(ids), 'r_med': float(np.median(r0)), 'r_max': float(r0.max()),
                          'wmin': float(wmax[ids].min())}
            else:
                per[k] = {'n': 0}
        print('[I] %-5s %-6s rigid verts per bone %s' % (side, f, json.dumps(per)))
        REP[side][f] = per
R['purity'] = {'pure': int((wmax > 0.999).sum()), 'n': n, 'mean_inf': float(ngrp.mean())}
R['hand'] = REP

# islands within hand region (per side) -> is the finger segmented?
par = list(range(n))
def find(a):
    while par[a] != a:
        par[a] = par[par[a]]; a = par[a]
    return a
for e in me.edges:
    a, b = find(e.vertices[0]), find(e.vertices[1])
    if a != b: par[a] = b
isl = defaultdict(list)
for i in range(n): isl[find(i)].append(i)
sizes = sorted((len(v) for v in isl.values()), reverse=True)
print('[I] islands on body: %d  sizes top12 %s' % (len(isl), sizes[:12]))
R['islands'] = {'count': len(isl), 'top': sizes[:20]}
json.dump(R, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[I] DONE')
