# -*- coding: utf-8 -*-
"""j1: prove additive-only. Compare source blend vs built blend per mesh:
existing-vertex max|d|, existing poly vertex tuples, per-vertex vgroup weights, UV arrays
for loops of pre-existing polys, material lists, object list, bone set, action curves.
"""
import bpy, sys, os, json
import numpy as np

ARGS = sys.argv[sys.argv.index('--') + 1:]
SRC, DST, OUT = ARGS[0], ARGS[1], ARGS[2]


def snap():
    d = {}
    for ob in bpy.data.objects:
        rec = {'type': ob.type, 'data': (ob.data.name if ob.data else None)}
        if ob.type == 'MESH':
            me = ob.data
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            rec['co'] = co.reshape(-1, 3)
            rec['polys'] = [tuple(p.vertices) for p in me.polygons]
            rec['mats'] = [m.name if m else None for m in me.materials]
            rec['nloops'] = len(me.loops)
            uvs = {}
            for l in me.uv_layers:
                a = np.empty(len(me.loops) * 2)
                l.data.foreach_get('uv', a)
                uvs[l.name] = a
            rec['uvs'] = uvs
            w = []
            for v in me.vertices:
                w.append(tuple(sorted((g.group, round(g.weight, 9)) for g in v.groups)))
            rec['w'] = w
            rec['groups'] = [g.name for g in ob.vertex_groups]
            rec['mods'] = [(m.type, getattr(m, 'object', None).name if getattr(m, 'object', None) else None) for m in ob.modifiers]
        elif ob.type == 'ARMATURE':
            rec['bones'] = [(b.name, b.use_deform) for b in ob.data.bones]
            rec['scale'] = tuple(ob.scale)
        d[ob.name] = rec
    acts = {}
    for a in bpy.data.actions:
        n = 0
        try:
            n = len(a.fcurves)
        except Exception:
            for lay in a.layers:
                for st in lay.strips:
                    for cb in getattr(st, 'channelbags', []):
                        n += len(cb.fcurves)
        acts[a.name] = n
    return d, acts


bpy.ops.wm.open_mainfile(filepath=SRC)
A, ACA = snap()
bpy.ops.wm.open_mainfile(filepath=DST)
B, ACB = snap()

rep = {'src': SRC, 'dst': DST, 'objects_ok': sorted(A) == sorted(B), 'missing': sorted(set(A) - set(B)),
       'extra': sorted(set(B) - set(A)), 'actions_src': ACA, 'actions_dst': ACB, 'meshes': {}}
ok = True
for name in sorted(A):
    a, b = A[name], B[name]
    r = {'type': a['type']}
    if a['type'] == 'MESH':
        n0 = len(a['co'])
        n1 = len(b['co'])
        dmax = float(np.abs(a['co'] - b['co'][:n0]).max()) if n1 >= n0 else 9e9
        r['nv'] = [n0, n1]
        r['np'] = [len(a['polys']), len(b['polys'])]
        r['orig_max_abs_delta'] = dmax
        r['polys_unchanged'] = a['polys'] == b['polys'][:len(a['polys'])]
        r['mats_src'] = a['mats']
        r['mats_dst'] = b['mats']
        r['mats_ok'] = a['mats'] == b['mats']
        uvok = {}
        for k, arr in a['uvs'].items():
            nb = b['uvs'].get(k)
            uvok[k] = bool(nb is not None and nb.shape[0] >= arr.shape[0] and np.array_equal(arr, nb[:arr.shape[0]]))
        r['uv_layers'] = list(a['uvs'])
        r['uv_unchanged'] = uvok
        r['w_unchanged'] = a['w'] == b['w'][:len(a['w'])]
        r['w_n'] = [len(a['w']), len(b['w'])]
        r['groups_src'] = len(a['groups'])
        r['groups_dst'] = len(b['groups'])
        r['new_tris'] = int(sum(len(p) - 2 for p in b['polys'][len(a['polys']):]))
        r['mods_ok'] = a['mods'] == b['mods']
        r['pass'] = (dmax <= 1e-9 and r['polys_unchanged'] and r['mats_ok'] and all(uvok.values())
                     and r['w_unchanged'] and r['mods_ok'])
    elif a['type'] == 'ARMATURE':
        r['bones_src'] = len(a['bones'])
        r['bones_dst'] = len(b['bones'])
        r['deform_src'] = sum(1 for n, df in a['bones'] if df)
        r['deform_dst'] = sum(1 for n, df in b['bones'] if df)
        r['bones_ok'] = a['bones'] == b['bones']
        r['scale'] = [a['scale'], b['scale']]
        r['pass'] = r['bones_ok'] and a['scale'] == b['scale']
    else:
        r['pass'] = True
    ok = ok and r['pass']
    rep['meshes'][name] = r
    print('[V] %-24s %s %s' % (name, a['type'], {k: v for k, v in r.items() if k in
          ('nv', 'np', 'orig_max_abs_delta', 'polys_unchanged', 'uv_unchanged', 'w_unchanged', 'new_tris', 'mats_ok', 'pass', 'bones_src', 'bones_dst', 'deform_dst', 'bones_ok', 'scale')}),
          flush=True)
rep['all_pass'] = bool(ok and rep['objects_ok'] and ACA == ACB)
json.dump(rep, open(OUT, 'w'), indent=1)
print('[V] ALL_PASS', rep['all_pass'], '->', OUT)
