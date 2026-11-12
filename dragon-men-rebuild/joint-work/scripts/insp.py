# -*- coding: utf-8 -*-
"""Inspect the source blend: objects, meshes, bones, action, joint candidate geometry."""
import bpy, os, json, sys
import numpy as np

SRC = r'D:\ai\建模\dragon-men-rebuild\hand-work\ark\DragonMan_Hands_joint.blend'
OUT = r'D:\ai\建模\dragon-men-rebuild\joint-work\verify\insp.json'
bpy.ops.wm.open_mainfile(filepath=SRC)
print('[I] objects:', [(o.name, o.type) for o in bpy.data.objects])
d = {}
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    me = o.data
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    MW = np.array(o.matrix_world)
    W = co @ MW[:3, :3].T + MW[:3, 3]
    tri = sum(len(p.vertices) - 2 for p in me.polygons)
    mats = [m.name for m in me.materials]
    mtally = {}
    for p in me.polygons:
        nm = mats[p.material_index] if p.material_index < len(mats) else '?'
        mtally[nm] = mtally.get(nm, 0) + 1
    d[o.name] = dict(nv=len(me.vertices), npol=len(me.polygons), tris=tri, mats=mats, mtally=mtally,
                     uvs=[l.name for l in me.uv_layers],
                     bbox_min=W.min(axis=0).tolist(), bbox_max=W.max(axis=0).tolist(),
                     mods=[(m.type, getattr(m, 'object', None).name if getattr(m, 'object', None) else None) for m in o.modifiers],
                     vgroups=len(o.vertex_groups), MW=MW.tolist(), scale=list(o.scale), parent=(o.parent.name if o.parent else None))
arm = bpy.data.objects['DragonMan_Rig']
print('[I] arm matrix_world', [round(x, 4) for x in arm.matrix_world.to_translation()], 'scale', list(arm.scale))
an = arm.animation_data.action if arm.animation_data else None
def nfc(a):
    c = 0
    for lay in getattr(a, 'layers', []):
        for st in lay.strips:
            for cb in getattr(st, 'channelbags', []):
                c += len(cb.fcurves)
    return c
d['_arm'] = dict(bones=len(arm.data.bones), deform=sum(1 for b in arm.data.bones if b.use_deform),
                 action=(an.name if an else None), fcurves=(nfc(an) if an else 0),
                 pose_scale=[list(pb.scale) for pb in arm.pose.bones][:3])
bones = []
for b in arm.data.bones:
    bones.append(dict(name=b.name, parent=(b.parent.name if b.parent else None), deform=b.use_deform,
                      head=list(arm.matrix_world @ b.head_local), tail=list(arm.matrix_world @ b.tail_local)))
d['_bones'] = bones
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(d, open(OUT, 'w'), indent=1)
for k, v in d.items():
    if k.startswith('_'):
        continue
    print('[I] %-20s nv=%6d npol=%5d tris=%5d mats=%s uvs=%s' % (k, v['nv'], v['npol'], v['tris'], v['mats'], v['uvs']))
print('[I] arm', d['_arm'])
with open(os.path.join(os.path.dirname(OUT), 'bones.txt'), 'w', encoding='utf-8') as f:
    for b in bones:
        f.write('%-34s par=%-30s def=%d head=(%.4f,%.4f,%.4f) tail=(%.4f,%.4f,%.4f)\n' % (
            b['name'], b['parent'], b['deform'], b['head'][0], b['head'][1], b['head'][2], b['tail'][0], b['tail'][1], b['tail'][2]))
print('[I] DONE')
