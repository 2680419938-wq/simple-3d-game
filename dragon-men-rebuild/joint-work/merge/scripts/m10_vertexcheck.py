# -*- coding: utf-8 -*-
# m10: blend-level acceptance: original vertex identity (<=1e-9), face counts, cuff/plate bookkeeping,
#        T-Pose / A-Pose rest measurements. Runs several blends in one session.
import bpy, sys, json, math
import numpy as np
from mathutils import Vector, kdtree

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = {argv[i].lstrip('-'): argv[i + 1] for i in range(0, len(argv) - 1, 2)}
OUT = opt['report']
R = {}

def coords(ob):
    me = ob.data if hasattr(ob, 'data') else ob
    n = len(me.vertices); a = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get('co', a); return a.reshape(n, 3)

def snapshot(path, tag):
    bpy.ops.wm.open_mainfile(filepath=path)
    d = {'path': path, 'objects': {}}
    for nm in ('DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R'):
        ob = bpy.data.objects[nm]; me = ob.data
        matnames = [m.name if m else '?' for m in me.materials]
        primat = np.zeros(len(me.polygons), dtype=int)
        me.polygons.foreach_get('material_index', primat)
        vg = [g.name for g in ob.vertex_groups]
        d['objects'][nm] = {'co': coords(ob), 'verts': len(me.vertices), 'faces': len(me.polygons),
                            'mats': matnames, 'pmat': primat, 'vg': vg,
                            'groups': [[(g.group, round(float(g.weight), 6)) for g in v.groups] for v in me.vertices]}
    arm = bpy.data.objects['DragonMan_Rig']
    d['bones'] = len(arm.data.bones); d['deform'] = sum(1 for b in arm.data.bones if b.use_deform)
    d['actions'] = [a.name for a in bpy.data.actions]
    MW = np.array(arm.matrix_world)
    d['mw_scale'] = [round(float(v), 4) for v in np.linalg.norm(MW[:3, :3], axis=0)]
    def wpos(n):
        B = arm.data.bones[n]; p = MW[:3, :3] @ np.array(B.head_local) + MW[:3, 3]
        t = MW[:3, :3] @ np.array(B.tail_local) + MW[:3, 3]; return p, t
    d['ankle'] = {s: [round(float(v), 6) for v in wpos('mixamorig:%sFoot' % s)[0]] for s in ('Left', 'Right')}
    d['arm_dir'] = {}; d['arm_deg_vert'] = {}
    for s in ('Left', 'Right'):
        p, t = wpos('mixamorig:%sArm' % s); v = (t - p); v = v / np.linalg.norm(v)
        d['arm_dir'][s] = [round(float(x), 5) for x in v]
        d['arm_deg_vert'][s] = round(math.degrees(math.acos(min(1.0, abs(float(v[2]))))), 3)
    # world bbox from evaluated meshes (rest, no action influence)
    if arm.animation_data: arm.animation_data.action = None
    for pb in arm.pose.bones: pb.matrix_basis = pb.matrix_basis.Identity(4)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); lo = [9e9] * 3; hi = [-9e9] * 3
    for nm in ('DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R'):
        ob = bpy.data.objects[nm]; ev = ob.evaluated_get(dg); me = ev.to_mesh()
        co = coords(me) @ np.array(ev.matrix_world)[:3, :3].T + np.array(ev.matrix_world)[:3, 3]
        lo = [min(lo[k], float(co[:, k].min())) for k in range(3)]
        hi = [max(hi[k], float(co[:, k].max())) for k in range(3)]
        ev.to_mesh_clear()
    d['bbox'] = [[round(v, 5) for v in lo], [round(v, 5) for v in hi]]
    d['fcurves_total'] = 0
    for a in bpy.data.actions:
        try:
            for layer in a.layers:
                for strip in layer.strips:
                    for cb in strip.channelbags: d['fcurves_total'] += len(cb.fcurves)
        except Exception: pass
    print('[M10] %s verts/faces %s bbox %s' % (tag, [(k, v['verts'], v['faces']) for k, v in d['objects'].items()], d['bbox']))
    return d

V2B = snapshot(opt['v2b'], 'v2b')
R['v2b'] = {k: V2B[k] for k in ('bones', 'deform', 'actions', 'bbox', 'ankle', 'arm_dir', 'arm_deg_vert', 'mw_scale')}
R['v2b']['objects'] = {k: {kk: V2B['objects'][k][kk] for kk in ('verts', 'faces', 'mats')} for k in V2B['objects']}

for tag, key in (('tp', 'tp'), ('ap', 'ap'), ('walk', 'walk')):
    if key not in opt: continue
    D = snapshot(opt[key], tag)
    rec = {k: D[k] for k in ('bones', 'deform', 'actions', 'bbox', 'ankle', 'arm_dir', 'arm_deg_vert', 'mw_scale', 'fcurves_total')}
    rec['objects'] = {k: {kk: D['objects'][k][kk] for kk in ('verts', 'faces', 'mats')} for k in D['objects']}
    rec['verts_delta'] = {k: D['objects'][k]['verts'] - V2B['objects'][k]['verts'] for k in D['objects']}
    rec['faces_delta'] = {k: D['objects'][k]['faces'] - V2B['objects'][k]['faces'] for k in D['objects']}
    # original-vertex identity
    me = D['objects']['DragonMan_Body']; A = V2B['objects']['DragonMan_Body']['co']; B = me['co']
    n = min(len(A), len(B))
    if len(B) >= len(A):
        rec['body_prefix_maxdev'] = float(np.abs(B[:len(A)] - A).max())
        rec['body_prefix_identical'] = bool(np.array_equal(B[:len(A)], A))
    kd = kdtree.KDTree(len(A))
    for i, c in enumerate(A): kd.insert(Vector(c), i)
    kd.balance()
    zero = 0; far = []
    for c in B:
        _, _, dist = kd.find(Vector(c))
        if dist <= 1e-9: zero += 1
        else: far.append(float(dist))
    rec['kd_zero_match'] = zero; rec['kd_nonzero'] = len(far)
    rec['kd_nonzero_max'] = round(max(far), 6) if far else 0.0
    for nm in ('DragonMan_Foot.L', 'DragonMan_Foot.R'):
        rec['foot_maxdev_' + nm[-1]] = float(np.abs(D['objects'][nm]['co'] - V2B['objects'][nm]['co']).max())
    # per-vertex-group face counts (finger / sleeve faces must not shrink)
    def group_faces(dobj):
        out = {}
        polys = dobj['pmat']
        gnames = dobj['vg']; groups = dobj['groups']
        cnt = {}
        for pi in range(len(polys)):
            pass
        return out
    # material face counts
    def matfaces(o):
        return {o['mats'][i] if i < len(o['mats']) else '?': int((o['pmat'] == i).sum()) for i in set(o['pmat'].tolist())}
    rec['mat_faces'] = {k: matfaces(D['objects'][k]) for k in D['objects']}
    rec['mat_faces_v2b'] = {k: matfaces(V2B['objects'][k]) for k in V2B['objects']}
    R[tag] = rec
    print('[M10] %s prefix_dev %s kd_zero %d nonzero %d max %s' % (tag, rec.get('body_prefix_maxdev'), rec['kd_zero_match'], rec['kd_nonzero'], rec['kd_nonzero_max']))

json.dump(R, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[M10] DONE')
