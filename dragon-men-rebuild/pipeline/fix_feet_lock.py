# fix_feet_lock.py -- keep the foot bones at their REST world orientation in Walk/Run so the claws stay pointing down
import bpy, sys, json, math
from mathutils import Matrix, Vector
a = sys.argv[sys.argv.index('--')+1:]
O = {}
i = 0
while i < len(a):
    if a[i].startswith('--'):
        k = a[i].lstrip('-'); v = a[i+1] if i+1 < len(a) and not a[i+1].startswith('--') else '1'
        O[k]=v; i += 2 if (i+1 < len(a) and not a[i+1].startswith('--')) else 1
    else: i += 1
SRC, OUTB, GLB = O['src'], O['out-blend'], O.get('out-glb')
FEET = ['mixamorig:LeftFoot','mixamorig:RightFoot']
TOES = ['mixamorig:LeftToeBase','mixamorig:LeftToeEnd','mixamorig:LeftToe02End','mixamorig:LeftToe02End.001',
        'mixamorig:LeftToe03Base','mixamorig:LeftToe03End','mixamorig:RightToeBase','mixamorig:RightToeEnd',
        'mixamorig:RightToe02End','mixamorig:RightToe02End.001','mixamorig:RightToe03Base','mixamorig:RightToe03End']
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
rest_rot = {b.name: b.matrix_local.to_3x3().normalized() for b in arm.data.bones}
report = {}
for act_name in ('Walk','Run'):
    act = bpy.data.actions.get(act_name)
    if not act: continue
    arm.animation_data.action = act
    fr = [int(round(x)) for x in act.frame_range]
    frames = list(range(fr[0], fr[1]+1))
    for f in frames:
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        for fb in FEET:
            pb = arm.pose.bones[fb]
            cur = pb.matrix
            want = rest_rot[fb].to_4x4()
            want.translation = cur.translation
            pb.matrix = want
            bpy.context.view_layer.update()
            pb.keyframe_insert('rotation_quaternion', frame=f)
            pb.keyframe_insert('location', frame=f)
        # toes: zero out any basis rotation so they just follow the foot
        for tb in TOES:
            pb = arm.pose.bones[tb]
            pb.rotation_quaternion = (1,0,0,0)
            pb.location = (0,0,0)
            pb.keyframe_insert('rotation_quaternion', frame=f)
            pb.keyframe_insert('location', frame=f)
    report[act_name] = {'frames': len(frames), 'range': fr}
    print('[FL2]', act_name, json.dumps(report[act_name]))
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[FL2] saved', OUTB)
if GLB:
    COMMON = dict(export_format='GLB', use_selection=True, use_visible=False, export_apply=False,
        export_yup=True, export_texcoords=True, export_normals=True, export_tangents=False,
        export_materials='EXPORT', export_image_format='JPEG', export_image_quality=90,
        export_jpeg_quality=90, export_skins=True, export_def_bones=True, export_influence_nb=4,
        export_all_influences=False, export_rest_position_armature=True, export_leaf_bone=False,
        export_hierarchy_flatten_bones=False, export_anim_slide_to_zero=True, export_frame_range=False,
        export_optimize_animation_size=False, export_optimize_animation_keep_anim_armature=True,
        export_animation_mode='ACTIONS', export_anim_single_armature=True, export_force_sampling=True,
        export_morph=False, export_cameras=False, export_lights=False, export_extras=False, export_animations=True)
    for o in bpy.data.objects: o.select_set(False)
    for n in ('DragonMan_Body','DragonMan_Foot.L','DragonMan_Foot.R'): bpy.data.objects[n].select_set(True)
    arm.select_set(True); bpy.context.view_layer.objects.active = arm
    for x in bpy.data.actions: x.use_fake_user = True
    bpy.ops.export_scene.gltf(filepath=GLB, **COMMON)
    print('[FL2] exported', GLB)
