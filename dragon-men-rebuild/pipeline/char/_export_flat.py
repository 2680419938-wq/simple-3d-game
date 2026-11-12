import bpy
from mathutils import Vector, Matrix
P=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody/char_rig.blend'
Q=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody/char_rig_flat.blend'
GLB=r'D:/ai/建模/dragon-man-final/DragonMan_New.glb'
bpy.ops.wm.open_mainfile(filepath=P)
h=bpy.data.objects['Human']
for o in bpy.context.selected_objects: o.select_set(False)
h.select_set(True); bpy.context.view_layer.objects.active=h
bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
print('KEYS after', h.data.shape_keys)
bpy.context.view_layer.update()
zs=[(h.matrix_world@v.co).z for v in h.data.vertices]
print('FLAT z %.3f..%.3f n=%d'%(min(zs),max(zs),len(h.data.vertices)))
rig=bpy.data.objects['Human.rig']
for b in rig.pose.bones: b.rotation_mode='QUATERNION'; b.rotation_quaternion=(1,0,0,0)
sc=bpy.context.scene; sc.frame_start=1; sc.frame_end=33
bpy.ops.wm.save_as_mainfile(filepath=Q)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', export_apply=False, export_animations=True,
    export_animation_mode='ACTIONS', export_frame_range=False, export_bake_animation=True)
import os; print('GLB',os.path.getsize(GLB))
print('DONE')