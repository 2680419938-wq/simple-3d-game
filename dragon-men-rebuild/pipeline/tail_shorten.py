# tail_shorten.py -- uniformly scale the tail chain (bones + skinned verts) about the tail root.
# usage: blender -b --python tail_shorten.py -- --src A.blend --out-blend B.blend [--out-glb C.glb] [--k 0.45] [--anims Idle_Lively,Run,Walk]
import bpy, sys, os, json, math
from mathutils import Vector

def opts():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    d = {}
    i = 0
    while i < len(a):
        if a[i].startswith('--'):
            k = a[i].lstrip('-')
            v = a[i + 1] if i + 1 < len(a) and not a[i + 1].startswith('--') else '1'
            d[k] = v
            i += 2 if (i + 1 < len(a) and not a[i + 1].startswith('--')) else 1
        else:
            i += 1
    return d

O = opts()
SRC = O['src']; OUTB = O.get('out-blend', SRC.replace('.blend', '_tail.blend'))
GLB = O.get('out-glb')
K = float(O.get('k', '0.45'))
ANIMS = [s for s in O.get('anims', '').split(',') if s]
REPORT = O.get('report')

bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
sc.render.fps, sc.render.fps_base = 30, 1.0
arm = bpy.data.objects['DragonMan_Rig']
MESHES = [bpy.data.objects[n] for n in ('DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R')]

tail_names = [b.name for b in arm.data.bones if 'tail' in b.name.lower()]
B_local = arm.data.bones['mixamorig:tail.001'].head_local.copy()
B_world = arm.matrix_world @ B_local
print('[TS] tail bones', len(tail_names), 'root', tuple(round(v, 3) for v in B_world), 'k', K)

before = {'tail_tip_y': None, 'bbox': None}
def mesh_bbox():
    mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9))
    for ob in MESHES:
        for v in ob.data.vertices:
            co = ob.matrix_world @ v.co
            for i in range(3):
                mn[i] = min(mn[i], co[i]); mx[i] = max(mx[i], co[i])
    return mn, mx
mn0, mx0 = mesh_bbox()
before['bbox'] = [round(v, 3) for v in mn0] + [round(v, 3) for v in mx0]
print('[TS] bbox before', before['bbox'])

# --- bones ---
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
for n in tail_names:
    b = eb[n]
    b.head = B_local + (b.head - B_local) * K
    b.tail = B_local + (b.tail - B_local) * K
bpy.ops.object.mode_set(mode='OBJECT')

# --- mesh: scale by tail weight so the pelvis/tail boundary blends ---
gi_all = {ob.name: set(g.index for g in ob.vertex_groups if g.name in set(tail_names)) for ob in MESHES}
scaled = 0
for ob in MESHES:
    gi = gi_all[ob.name]
    if not gi:
        continue
    Minv = ob.matrix_world.inverted()
    for v in ob.data.vertices:
        w = sum(g.weight for g in v.groups if g.group in gi)
        if w <= 1e-6:
            continue
        w = min(1.0, w)
        co_w = ob.matrix_world @ v.co
        target_w = B_world + (co_w - B_world) * K
        v.co = Minv @ (co_w + (target_w - co_w) * w)
        scaled += 1
print('[TS] scaled verts', scaled)

mn1, mx1 = mesh_bbox()
print('[TS] bbox after', [round(v, 3) for v in mn1] + [round(v, 3) for v in mx1])
tip = arm.matrix_world @ arm.data.bones['mixamorig:Tail006b'].tail_local
print('[TS] tail tip now', tuple(round(v, 3) for v in tip))

# --- per-frame lowest vertex for each kept action ---
import numpy as np
dg = bpy.context.evaluated_depsgraph_get()
def minz(f):
    sc.frame_set(f)
    dg.update()
    lo = 1e9
    for ob in MESHES:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float32); me.vertices.foreach_get('co', co)
        co = co.reshape(n, 3); M = np.array(ev.matrix_world)
        w = co @ M[:3, :3].T + M[:3, 3]
        lo = min(lo, float(w[:, 2].min()))
        ev.to_mesh_clear()
    return lo

stats = {}
for a in list(bpy.data.actions):
    if ANIMS and a.name not in ANIMS:
        continue
    arm.animation_data.action = a
    f0, f1 = int(a.frame_range[0]), int(a.frame_range[1])
    vals = [minz(f) for f in range(f0, f1 + 1)]
    stats[a.name] = {'frames': f1 - f0 + 1, 'minz': round(min(vals), 5), 'maxz': round(max(vals), 5)}
    print('[TS] action', a.name, stats[a.name])
acts = list(bpy.data.actions)
if acts:
    arm.animation_data.action = bpy.data.actions.get('Idle_Lively') or acts[0]
    sc.frame_start, sc.frame_end = 1, int(arm.animation_data.action.frame_range[1])
else:
    sc.frame_start, sc.frame_end = 1, 1

bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[TS] saved', OUTB)

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
    for o in bpy.data.objects:
        o.select_set(False)
    for o in MESHES + [arm]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    keep = set(ANIMS) if ANIMS else set(a.name for a in bpy.data.actions)
    for a in list(bpy.data.actions):
        if a.name in keep:
            a.use_fake_user = True
        else:
            bpy.data.actions.remove(a)
    kw = dict(COMMON); kw['export_animations'] = bool(keep)
    bpy.ops.export_scene.gltf(filepath=GLB, **kw)
    print('[TS] exported', GLB, os.path.getsize(GLB))

if REPORT:
    json.dump({'src': SRC, 'k': K, 'bbox_before': before['bbox'],
               'bbox_after': [round(v, 3) for v in mn1] + [round(v, 3) for v in mx1],
               'tail_tip': [round(v, 3) for v in tip], 'scaled_verts': scaled,
               'actions': stats, 'blend': OUTB, 'glb': GLB}, open(REPORT, 'w', encoding='utf-8'), indent=1)
    print('[TS] report', REPORT)
