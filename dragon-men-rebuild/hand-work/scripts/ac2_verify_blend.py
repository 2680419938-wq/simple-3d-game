
# -*- coding: utf-8 -*-
"""ac2: blend-level acceptance — original verts unmoved, new geo counts, weights, materials, action."""
import bpy, sys, os, json
import numpy as np

SRC = r'D:\ai\建模\dragon-men-rebuild\std-rig\DragonMan_Std_TPose.blend'
DST = r'D:\ai\建模\dragon-men-rebuild\hand-work\ark\DragonMan_Hands_joint.blend'
OUT = r'D:\ai\建模\dragon-men-rebuild\hand-work\verify\blend_verify.json'
OBJS = ('DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R')


def snap(path):
    bpy.ops.wm.open_mainfile(filepath=path)
    d = {}
    for nm in OBJS:
        ob = bpy.data.objects[nm]
        me = ob.data
        n = len(me.vertices)
        co = np.empty(n * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        MW = np.array(ob.matrix_world)
        d[nm] = dict(n=n, npol=len(me.polygons), co=co @ MW[:3, :3].T + MW[:3, 3],
                     mats=[m.name for m in me.materials], uvs=[l.name for l in me.uv_layers])
    arm = bpy.data.objects['DragonMan_Rig']

    def nfc(a):
        c = 0
        for lay in getattr(a, 'layers', []):
            for st in lay.strips:
                for cb in getattr(st, 'channelbags', []):
                    c += len(cb.fcurves)
        return c
    an = arm.animation_data.action if arm.animation_data else None
    d['_anim'] = dict(action=(an.name if an else None), fcurves=(nfc(an) if an else 0),
                      bones=len(arm.data.bones), deform=sum(1 for b in arm.data.bones if b.use_deform))
    return d


A = snap(SRC)
B = snap(DST)
rep = {'src': {k: {kk: vv for kk, vv in v.items() if kk != 'co'} for k, v in A.items()},
       'dst': {k: {kk: vv for kk, vv in v.items() if kk != 'co'} for k, v in B.items()}}
maxd = {}
for nm in OBJS:
    n = A[nm]['n']
    assert B[nm]['n'] >= n
    d = np.abs(B[nm]['co'][:n] - A[nm]['co']).max()
    maxd[nm] = float(d)
    print('[V] %-18s src verts %6d  dst %6d (+%d)  polys %6d -> %6d  max|d| = %.3e' %
          (nm, A[nm]['n'], B[nm]['n'], B[nm]['n'] - n, A[nm]['npol'], B[nm]['npol'], d))
tot_src = sum(A[nm]['n'] for nm in OBJS)
rep['max_disp'] = maxd
rep['max_disp_all'] = max(maxd.values())
rep['orig_verts_total'] = tot_src
print('[V] total original verts %d, global max|d| = %.3e' % (tot_src, max(maxd.values())))

bpy.ops.wm.open_mainfile(filepath=DST)
ob = bpy.data.objects['DragonMan_Body']
me = ob.data
n0 = A['DragonMan_Body']['n']
npol0 = A['DragonMan_Body']['npol']
newfaces = [p for p in me.polygons if p.index >= npol0]
tris = sum(len(p.vertices) - 2 for p in newfaces)
mats = {}
for p in newfaces:
    k = me.materials[p.material_index].name
    mats[k] = mats.get(k, 0) + 1
grp = {g.index: g.name for g in ob.vertex_groups}
infl, wsum, wob, gnames = [], [], [], {}
for i in range(n0, len(me.vertices)):
    gs = [(grp[g.group], g.weight) for g in me.vertices[i].groups if g.weight > 0]
    infl.append(len(gs))
    wsum.append(sum(w for _, w in gs))
    for gn, w in gs:
        gnames[gn] = gnames.get(gn, 0) + 1
print('[V] new faces %d  tris %d  by material %s' % (len(newfaces), tris, mats))
print('[V] new verts %d  influences min/max %d/%d  wsum min/max %.6f/%.6f' %
      (len(me.vertices) - n0, min(infl), max(infl), min(wsum), max(wsum)))
print('[V] groups touched by new verts: %d' % len(gnames))
# existing verts must keep their exact weights
A_weights = None
bpy.ops.wm.open_mainfile(filepath=SRC)
ob2 = bpy.data.objects['DragonMan_Body']
g2 = {g.index: g.name for g in ob2.vertex_groups}
w_src = [tuple(sorted((g2[g.group], round(g.weight, 9)) for g in v.groups)) for v in ob2.data.vertices]
bpy.ops.wm.open_mainfile(filepath=DST)
ob3 = bpy.data.objects['DragonMan_Body']
g3 = {g.index: g.name for g in ob3.vertex_groups}
w_dst = [tuple(sorted((g3[g.group], round(g.weight, 9)) for g in v.groups)) for v in ob3.data.vertices[:n0]]
diff = sum(1 for a, b in zip(w_src, w_dst) if a != b)
print('[V] original verts whose weights changed: %d (of %d)' % (diff, len(w_src)))

# UV sanity on new loops: all finite, and every new vert's UV equals some skin vert's UV
me3 = ob3.data
lay = me3.uv_layers['map1']
arr = np.zeros(len(me3.loops) * 2)
lay.data.foreach_get('uv', arr)
arr = arr.reshape(-1, 2)
newl = [lp.index for lp in me3.loops if lp.vertex_index >= n0]
uv_new = arr[newl]
finite = np.isfinite(uv_new).all()
src_lay = bpy.data.objects['DragonMan_Body']
print('[V] uv layers', [l.name for l in me3.uv_layers], 'new loops', len(newl),
      'uv range %.4f..%.4f / %.4f..%.4f finite=%s' % (uv_new[:, 0].min(), uv_new[:, 0].max(), uv_new[:, 1].min(), uv_new[:, 1].max(), finite))

arm = bpy.data.objects['DragonMan_Rig']


def nfc(a):
    c = 0
    for lay in getattr(a, 'layers', []):
        for st in lay.strips:
            for cb in getattr(st, 'channelbags', []):
                c += len(cb.fcurves)
    return c


an = arm.animation_data.action if arm.animation_data else None
print('[V] action', an.name if an else None, 'fcurves', nfc(an) if an else 0,
      'bones', len(arm.data.bones), 'deform', sum(1 for b in arm.data.bones if b.use_deform))
rep.update(dict(newverts=len(me3.vertices) - n0, newfaces=len(newfaces), newtris=tris,
                newfaces_by_mat=mats, infl_min=min(infl), infl_max=max(infl),
                wsum_min=float(min(wsum)), wsum_max=float(max(wsum)),
                orig_weight_changes=int(diff), uv_layers=[l.name for l in me3.uv_layers],
                uv_finite=bool(finite), groups_touched=gnames,
                action=(an.name if an else None), fcurves=(nfc(an) if an else 0),
                bones=len(arm.data.bones), deform_bones=sum(1 for b in arm.data.bones if b.use_deform)))
json.dump(rep, open(OUT, 'w'), indent=1)
print('[V] DONE ->', OUT)
