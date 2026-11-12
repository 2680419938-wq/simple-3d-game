# -*- coding: utf-8 -*-
# m4: export one deliverable GLB from a merge blend, using the j5_export COMMON parameters.
import bpy, sys, os, json

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = {argv[i].lstrip('-'): argv[i + 1] for i in range(0, len(argv) - 1, 2)}
SRC = opt['src']; OUT = opt['out']; MODE = opt.get('mode', 'walk')

COMMON = dict(export_format='GLB', use_selection=True, use_visible=False, export_apply=False,
    export_yup=True, export_texcoords=True, export_normals=True, export_tangents=False,
    export_materials='EXPORT', export_image_format='JPEG', export_image_quality=90,
    export_jpeg_quality=90, export_skins=True, export_def_bones=True, export_influence_nb=4,
    export_all_influences=False, export_rest_position_armature=True, export_leaf_bone=False,
    export_hierarchy_flatten_bones=False, export_anim_slide_to_zero=True, export_frame_range=False,
    export_optimize_animation_size=False, export_optimize_animation_keep_anim_armature=True,
    export_animation_mode='ACTIONS', export_anim_single_armature=True, export_force_sampling=True,
    export_morph=False, export_cameras=False, export_lights=False, export_extras=False)

bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene; sc.render.fps, sc.render.fps_base = 30, 1.0
arm = bpy.data.objects['DragonMan_Rig']
keep = ['DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R', 'DragonMan_Rig']
for o in bpy.data.objects: o.select_set(False)
sel = [bpy.data.objects[n] for n in keep]
for o in sel: o.select_set(True)
bpy.context.view_layer.objects.active = arm
kw = dict(COMMON)
if MODE == 'apose':
    for a in bpy.data.actions: a.use_fake_user = False
    kw['export_animations'] = False
    if arm.animation_data: arm.animation_data.action = None
else:
    kw['export_animations'] = True
    if arm.animation_data is None: arm.animation_data_create()
    if arm.animation_data.action is None:
        arm.animation_data.action = bpy.data.actions.get('Idle_Lively')
for a in bpy.data.actions: a.use_fake_user = True
print('[M4] mode', MODE, 'actions', [(a.name, [round(v, 2) for v in a.frame_range]) for a in bpy.data.actions])
bpy.ops.export_scene.gltf(filepath=OUT, **kw)
print('[M4] wrote', OUT, os.path.getsize(OUT), 'bytes')
json.dump({'src': SRC, 'out': OUT, 'mode': MODE, 'bytes': os.path.getsize(OUT),
           'kw': {k: (v if isinstance(v, (int, float, str, bool)) else str(v)) for k, v in kw.items()},
           'actions': [a.name for a in bpy.data.actions]},
          open(opt['report'], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[M4] DONE')
