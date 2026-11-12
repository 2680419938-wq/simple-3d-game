# fix_feet_caps.py -- (A) feet keep their rest orientation relative to the shin in Walk/Run
#                      (B) cap open leg-tube rims so bent knees don't reveal hollow interiors
import bpy, bmesh, sys, os, json, math
from mathutils import Quaternion, Vector
a = sys.argv[sys.argv.index('--') + 1:]
O = {}
i = 0
while i < len(a):
    if a[i].startswith('--'):
        k = a[i].lstrip('-'); v = a[i + 1] if i + 1 < len(a) and not a[i + 1].startswith('--') else '1'
        O[k] = v; i += 2 if (i + 1 < len(a) and not a[i + 1].startswith('--')) else 1
    else:
        i += 1
SRC, OUTB, GLB = O['src'], O['out-blend'], O.get('out-glb')
FOOT_BONES = [b for b in ('LeftFoot', 'LeftToeBase', 'LeftToeEnd', 'LeftToe02End', 'LeftToe02End.001',
                          'LeftToe03Base', 'LeftToe03End', 'RightFoot', 'RightToeBase', 'RightToeEnd',
                          'RightToe02End', 'RightToe02End.001', 'RightToe03Base', 'RightToe03End')]

bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
report = {'feet': {}, 'caps': {}}

def all_fcurves(act):
    if hasattr(act, 'fcurves'):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out

for act_name in ('Walk', 'Run'):
    act = bpy.data.actions.get(act_name)
    if not act:
        continue
    keep = 0
    for fc in all_fcurves(act):
        dp = fc.data_path
        if not dp.endswith('.rotation_quaternion'):
            continue
        bone = dp.split('"')[1]
        if bone.split(':')[-1] in FOOT_BONES:
            for kp in fc.keyframe_points:
                kp.co[1] = 1.0 if fc.array_index == 0 else 0.0
                kp.handle_left[1] = kp.co[1]
                kp.handle_right[1] = kp.co[1]
            keep += 1
    report['feet'][act_name] = {'channels_reset': keep}

# ---- B: cap open rims of the leg tubes ----
body = bpy.data.objects['DragonMan_Body']
me = body.data
bm = bmesh.new(); bm.from_mesh(me)
boundary = [e for e in bm.edges if len(e.link_faces) == 1]
loops = []
seen = set()
for e in boundary:
    if e.index in seen:
        continue
    stack = [e]; comp = []
    while stack:
        cur = stack.pop()
        if cur.index in seen:
            continue
        seen.add(cur.index); comp.append(cur)
        for v in cur.verts:
            for e2 in v.link_edges:
                if e2.index not in seen and len(e2.link_faces) == 1:
                    stack.append(e2)
    loops.append(comp)
loops.sort(key=lambda c: -len(c))
info = []
filled = 0
for comp in loops:
    verts = set()
    for e in comp:
        verts.add(e.verts[0]); verts.add(e.verts[1])
    if not (6 <= len(verts) <= 160):
        continue
    c = sum((v.co for v in verts), Vector()) / len(verts)
    if c.z > 0.75 or c.z < 0.02:
        info.append({'n': len(verts), 'c': [round(x, 3) for x in c], 'filled': False})
        continue
    try:
        bmesh.ops.holes_fill(bm, edges=comp, sides=len(comp))
        filled += 1
        info.append({'n': len(verts), 'c': [round(x, 3) for x in c], 'filled': True})
    except Exception as ex:
        info.append({'n': len(verts), 'c': [round(x, 3) for x in c], 'err': str(ex)})
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(me); bm.free()
report['caps'] = {'loops': len(loops), 'filled': filled, 'detail': info[:12]}
print('[FC]', json.dumps(report, ensure_ascii=False)[:900])

bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[FC] saved', OUTB)
if GLB:
    COMMON = dict(export_format='GLB', use_selection=True, use_visible=False, export_apply=False,
        export_yup=True, export_texcoords=True, export_normals=True, export_tangents=False,
        export_materials='EXPORT', export_image_format='JPEG', export_image_quality=90,
        export_jpeg_quality=90, export_skins=True, export_def_bones=True, export_influence_nb=4,
        export_all_influences=False, export_rest_position_armature=True, export_leaf_bone=False,
        export_hierarchy_flatten_bones=False, export_anim_slide_to_zero=True, export_frame_range=False,
        export_optimize_animation_size=False, export_optimize_animation_keep_anim_armature=True,
        export_animation_mode='ACTIONS', export_anim_single_armature=True, export_force_sampling=True,
        export_morph=False, export_cameras=False, export_lights=False, export_extras=False)
    meshes = [bpy.data.objects[n] for n in ('DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R')]
    for o in bpy.data.objects: o.select_set(False)
    for o in meshes + [arm]: o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    for x in bpy.data.actions: x.use_fake_user = True
    kw = dict(COMMON); kw['export_animations'] = True
    bpy.ops.export_scene.gltf(filepath=GLB, **kw)
    print('[FC] exported', GLB, os.path.getsize(GLB))
