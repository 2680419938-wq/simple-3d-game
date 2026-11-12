
# -*- coding: utf-8 -*-
"""ac3: export the built blend to GLB with the pipeline's std export settings."""
import bpy, sys, os, json

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
BLD = ARGS[0] if ARGS else r'D:\ai\建模\dragon-men-rebuild\hand-work\ark\DragonMan_Hands_joint.blend'
GLB = ARGS[1] if len(ARGS) > 1 else r'D:\ai\建模\dragon-men-rebuild\hand-work\DragonMan_Hands_joint.glb'
COMMON = dict(export_format='GLB', use_selection=True, use_visible=False, export_apply=False,
              export_yup=True, export_texcoords=True, export_normals=True, export_tangents=False,
              export_materials='EXPORT', export_image_format='JPEG', export_image_quality=90,
              export_jpeg_quality=90, export_skins=True, export_def_bones=True,
              export_influence_nb=4, export_all_influences=False,
              export_rest_position_armature=True, export_leaf_bone=False,
              export_hierarchy_flatten_bones=False, export_anim_slide_to_zero=True,
              export_frame_range=False, export_optimize_animation_size=False,
              export_optimize_animation_keep_anim_armature=True, export_animation_mode='ACTIONS',
              export_anim_single_armature=True, export_force_sampling=True, export_morph=False,
              export_cameras=False, export_lights=False, export_extras=False)

bpy.ops.wm.open_mainfile(filepath=BLD)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
want_anim = bool(arm.animation_data and arm.animation_data.action)
print('[E] anim', want_anim, (arm.animation_data.action.name if want_anim else None))
names = ['DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R', 'DragonMan_Rig']
bpy.ops.object.select_all(action='DESELECT')
for nm in names:
    ob = bpy.data.objects[nm]
    ob.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.gltf(filepath=GLB, export_animations=want_anim, **COMMON)
print('[E] size', os.path.getsize(GLB))
print('[E] DONE', GLB)
