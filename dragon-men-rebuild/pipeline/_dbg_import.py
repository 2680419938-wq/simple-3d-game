# -*- coding: utf-8 -*-
import bpy
from mathutils import Vector
sc = bpy.context.scene
sc.render.fps, sc.render.fps_base = 30, 1.0
bpy.ops.import_scene.gltf(filepath=r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb')
for o in bpy.data.objects:
    print('[D] obj %-18s type=%-8s parent=%s scale=%s loc=%s' % (o.name, o.type, o.parent.name if o.parent else None,
          [round(x,4) for x in o.scale], [round(x,4) for x in o.location]))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
print('[D] actions', [(a.name, tuple(round(x,1) for x in a.frame_range)) for a in bpy.data.actions])
print('[D] mesh verts', len(mesh.data.vertices), 'matrix_world', [round(x,4) for r in mesh.matrix_world for x in r])
print('[D] bound_box', [[round(c,4) for c in v] for v in mesh.bound_box][:2])
V = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
print('[D] world bbox min', [round(min(v[i] for v in V), 4) for i in range(3)],
      'max', [round(max(v[i] for v in V), 4) for i in range(3)])
def bh(n):
    return arm.matrix_world @ arm.data.bones[n].head_local
print('[D] foot.L', [round(x,4) for x in bh('foot.L')], 'toe.03.L', [round(x,4) for x in bh('toe.03.L')])
print('[D] arm matrix_world', [round(x,4) for r in arm.matrix_world for x in r])
ad = arm.animation_data
print('[D] anim_data', ad is not None, 'action', ad.action.name if ad and ad.action else None,
      'nla', [t.name for t in ad.nla_tracks] if ad else None)
