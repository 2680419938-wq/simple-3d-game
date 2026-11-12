# -*- coding: utf-8 -*-
# retarget_import.py -- bring an external humanoid clip (Mixamo FBX / BVH / any FBX with
# standard bone names) onto DragonMan's 70-bone rig, auto-fix ground/knee, export GLB.
# usage: blender -b --python retarget_import.py -- --src X.fbx --clip Run [--base ...] [--out-blend ...]
import bpy, sys, os, json, math
from mathutils import Vector, Matrix, Quaternion

def opt_map():
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

O = opt_map()
ROOT = r"D:\ai\建模"
BASE = O.get('base', ROOT + r"\dragon-men-rebuild\joint-work\merge\v3\DragonMan_Std_Run.blend")
SRC = O['src']
CLIP = O.get('clip') or os.path.splitext(os.path.basename(SRC))[0]
OUT_BLEND = O.get('out-blend', ROOT + r"\AnimLib\out\DragonMan_Std_" + CLIP + ".blend")
OUT_GLB = O.get('out-glb', ROOT + r"\AnimLib\out\DragonMan_Std_" + CLIP + ".glb")
REPORT = O.get('report', ROOT + r"\AnimLib\out\report_" + CLIP + ".json")
KNEE_LIMIT = float(O.get('knee', '90'))
GROUND = float(O.get('ground', '0'))
SRC_FPS = float(O.get('src-fps', '30'))
TAIL_SWAY = float(O.get('tail-sway', '5.0'))
STRIDE_SCALE = O.get('stride-scale', 'auto')
GROUND_PUSH = O.get('ground-push', '0')  # 0 = lift only (keeps flight phases), 1 = force contact
for p in (os.path.dirname(OUT_BLEND), os.path.dirname(OUT_GLB), os.path.dirname(REPORT)):
    os.makedirs(p, exist_ok=True)

def log(*a):
    print('[RET]', *a, flush=True)

# ---------- base ----------
bpy.ops.wm.open_mainfile(filepath=BASE)
sc = bpy.context.scene
sc.render.fps, sc.render.fps_base = 30, 1.0
arm = bpy.data.objects['DragonMan_Rig']
KEEP_ACTIONS = [a.name for a in bpy.data.actions]
MESHES = [bpy.data.objects[n] for n in ('DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R')]
bpy.context.view_layer.objects.active = arm

# ---------- import source ----------
before = set(o.name for o in bpy.data.objects)
ext = os.path.splitext(SRC)[1].lower()
if ext == '.fbx':
    bpy.ops.import_scene.fbx(filepath=SRC, use_anim=True, automatic_bone_orientation=False,
                             ignore_leaf_bones=True, global_scale=1.0)
elif ext == '.bvh':
    bpy.ops.import_anim.bvh(filepath=SRC, global_scale=1.0, use_fps_scale=False)
elif ext in ('.glb', '.gltf'):
    bpy.ops.import_scene.gltf(filepath=SRC)
else:
    raise SystemExit('unsupported source: ' + ext)
new = [o for o in bpy.data.objects if o.name not in before]
src_arms = [o for o in new if o.type == 'ARMATURE']
if not src_arms:
    raise SystemExit('no armature found in ' + SRC)
sarm = max(src_arms, key=lambda o: len(o.data.bones))
log('source armature', sarm.name, 'bones', len(sarm.data.bones), 'objects', [o.name for o in new][:6])

# ---------- name mapping ----------
SYN = {
    'pelvis': 'hips', 'root': 'root', 'cog': 'hips',
    'leftupperleg': 'leftupleg', 'leftlowerleg': 'leftleg', 'leftcalf': 'leftleg', 'leftthigh': 'leftupleg',
    'rightupperleg': 'rightupleg', 'rightlowerleg': 'rightleg', 'rightcalf': 'rightleg', 'rightthigh': 'rightupleg',
    'leftforearm': 'leftforearm', 'leftlowerarm': 'leftforearm', 'rightforearm': 'rightforearm', 'rightlowerarm': 'rightforearm',
    'leftupperarm': 'leftarm', 'rightupperarm': 'rightarm',
    'lefttoe': 'lefttoebase', 'righttoe': 'righttoebase', 'headtopend': 'headtopend',
    'hips2': 'hips',
}
def norm(n):
    s = n.split('|')[-1]
    s = s.replace('mixamorig', '').replace('mixamorig1', '').replace('mixamorig10', '')
    s = s.lower().replace(':', '').replace('_', '').replace(' ', '').replace('-', '')
    s = s.replace('.00', '').replace('.0', '').replace('.', '')
    return s
def canon(n):
    s = norm(n)
    if s in SYN:
        return SYN[s]
    return s

dst_bones = {b.name: b for b in arm.data.bones}
dst_by_canon = {}
for n in dst_bones:
    dst_by_canon.setdefault(canon(n), n)
src_by_canon = {}
for b in sarm.data.bones:
    src_by_canon.setdefault(canon(b.name), b)

MAP = {}
for c, db in dst_by_canon.items():
    if c in src_by_canon:
        MAP[db] = src_by_canon[c]
UNMAPPED_DST = [n for n in dst_bones if n not in MAP]
UNMAPPED_SRC = [b.name for c, b in src_by_canon.items() if c not in dst_by_canon]
log('mapped', len(MAP), 'unmapped dst', len(UNMAPPED_DST), 'unmapped src', len(UNMAPPED_SRC))
if len(MAP) < 12:
    raise SystemExit('too few bones matched: ' + str(list(MAP.items())[:10]))

# ---------- timing ----------
sact = sarm.animation_data.action if sarm.animation_data else None
if sact is None:
    raise SystemExit('source has no action')
f0, f1 = sact.frame_range
dur = max(1e-6, (f1 - f0) / SRC_FPS)
N = max(2, int(round(dur * 30.0)) + 1)
log('source frames', round(f0, 2), round(f1, 2), 'dur', round(dur, 4), '-> our frames', N)

# ---------- rest rotations (world) ----------
def rot3(m):
    q = m.to_quaternion()
    return q.to_matrix()
RD = {n: rot3(arm.matrix_world @ b.matrix_local) for n, b in dst_bones.items()}
RS = {b.name: rot3(sarm.matrix_world @ b.matrix_local) for b in sarm.data.bones}
RD_INV = {k: v.transposed() for k, v in RD.items()}
RS_INV = {k: v.transposed() for k, v in RS.items()}

parent_of = {n: (dst_bones[n].parent.name if dst_bones[n].parent else None) for n in dst_bones}
order = []
def walk(n):
    order.append(n)
    for c in dst_bones[n].children:
        walk(c.name)
for n in dst_bones:
    if parent_of[n] is None:
        walk(n)

PB = {n: arm.pose.bones[n] for n in dst_bones}
for pb in PB.values():
    pb.rotation_mode = 'QUATERNION'

HIPS = 'mixamorig:Hips'
s_hips = MAP.get(HIPS, None)
hips_rest_w = (arm.matrix_world @ dst_bones[HIPS].matrix_local).to_translation()
s_hips_rest_w = None
if s_hips is not None:
    s_hips_rest_w = (sarm.matrix_world @ s_hips.matrix_local).to_translation()

# ---------- vertical scale: ratio of leg lengths ----------
def wpos(obj, mw, bl):
    return (mw @ bl.head_local)
try:
    mw_d = arm.matrix_world
    our_leg = (wpos(arm, mw_d, dst_bones['mixamorig:LeftUpLeg']) - wpos(arm, mw_d, dst_bones['mixamorig:LeftLeg'])).length             + (wpos(arm, mw_d, dst_bones['mixamorig:LeftLeg']) - wpos(arm, mw_d, dst_bones['mixamorig:LeftFoot'])).length
    s_up = MAP.get('mixamorig:LeftUpLeg'); s_lo = MAP.get('mixamorig:LeftLeg'); s_ft = MAP.get('mixamorig:LeftFoot')
    mw_s = sarm.matrix_world
    src_leg = (wpos(sarm, mw_s, s_up) - wpos(sarm, mw_s, s_lo)).length + (wpos(sarm, mw_s, s_lo) - wpos(sarm, mw_s, s_ft)).length
    leg_ratio = our_leg / src_leg if src_leg > 1e-6 else 1.0
except Exception as e:
    log('leg ratio failed', e)
    leg_ratio = 1.0
if STRIDE_SCALE == 'auto':
    STRIDE_SCALE = leg_ratio
else:
    STRIDE_SCALE = float(STRIDE_SCALE)
log('leg len ours/src', round(our_leg, 4), round(src_leg, 4), 'ratio', round(leg_ratio, 4), 'stride scale', round(STRIDE_SCALE, 4))

# ---------- new action ----------
if arm.animation_data is None:
    arm.animation_data_create()
newact = bpy.data.actions.new(CLIP)
newact.use_fake_user = True
arm.animation_data.action = newact

KFR = {n: [] for n in dst_bones}
KLOC = None
frame_metrics = []

def clear_pose():
    for pb in PB.values():
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
        pb.location = Vector((0, 0, 0))
        pb.scale = Vector((1, 1, 1))

def set_frame_src(fr):
    fi = int(math.floor(fr))
    sc.frame_set(fi, subframe=fr - fi)

for i in range(N):
    t = i / (N - 1)
    fr = f0 + t * (f1 - f0)
    set_frame_src(fr)
    clear_pose()
    TW = {}
    for n in order:
        pb = sarm.pose.bones.get(MAP[n].name) if n in MAP else None
        if pb is not None:
            pose_rot = rot3(sarm.matrix_world @ pb.matrix)
            delta = pose_rot @ RS_INV[MAP[n].name]
            TW[n] = delta @ RD[n]
        else:
            p = parent_of[n]
            if p is None:
                TW[n] = RD[n]
            else:
                TW[n] = TW[p] @ (RD_INV[p] @ RD[n])
    # knee clamp (world-space bone direction, +Y is the bone axis)
    for side, bn in (('Left', 'mixamorig:LeftLeg'), ('Right', 'mixamorig:RightLeg')):
        up = 'mixamorig:%sUpLeg' % side
        du = TW[up] @ Vector((0, 1, 0))
        dl = TW[bn] @ Vector((0, 1, 0))
        flex = math.degrees(du.angle(dl))
        if flex > KNEE_LIMIT:
            par = TW[up]
            qb = (par @ (RD_INV[up] @ RD[bn])).inverted() @ TW[bn]
            qb = qb.to_quaternion()
            lo, hi = 0.0, 1.0
            for _ in range(12):
                s = (lo + hi) * 0.5
                tq = par @ (RD_INV[up] @ RD[bn]) @ Quaternion((1, 0, 0, 0)).slerp(qb, s).to_matrix()
                f2 = math.degrees(du.angle(tq @ Vector((0, 1, 0))))
                if f2 > KNEE_LIMIT:
                    hi = s
                else:
                    lo = s
            TW[bn] = par @ (RD_INV[up] @ RD[bn]) @ Quaternion((1, 0, 0, 0)).slerp(qb, lo).to_matrix()
    # tail: procedural sway on unmapped tail bones
    if TAIL_SWAY > 0:
        for n in order:
            if n in MAP:
                continue
            if 'tail' not in n.lower():
                continue
            idx = 1
            for k in range(1, 7):
                if ('%03d' % k) in n and ('00%d' % k) in n:
                    idx = k
            amp = math.radians(TAIL_SWAY) * (0.6 + 0.4 * idx / 6.0)
            phase = 2 * math.pi * t + idx * 0.5
            p = parent_of[n]
            base = TW[p] @ (RD_INV[p] @ RD[n]) if p else RD[n]
            TW[n] = base @ Matrix.Rotation(math.sin(phase) * amp, 3, 'Z') @ Matrix.Rotation(math.sin(phase * 2) * amp * 0.5, 3, 'X')
    # write local rotations
    for n in order:
        p = parent_of[n]
        rest_local = (RD_INV[p] @ RD[n]) if p else RD[n]
        pw = TW[p] if p else Matrix.Identity(3)
        q = (pw @ rest_local).inverted() @ TW[n]
        PB[n].rotation_quaternion = q.to_quaternion()
    bpy.context.view_layer.update()
    # hips translation
    if s_hips is not None:
        s_pose_w = (sarm.matrix_world @ sarm.pose.bones[s_hips.name].matrix).to_translation()
        dp = s_pose_w - s_hips_rest_w
        P_w = hips_rest_w + Vector((dp.x * STRIDE_SCALE, dp.y * STRIDE_SCALE, dp.z * STRIDE_SCALE))
        P_arm = arm.matrix_world.inverted() @ P_w
        mh = PB[HIPS].matrix.copy()
        mh.translation = P_arm
        PB[HIPS].matrix = mh
        bpy.context.view_layer.update()
    # keyframe
    for n in order:
        PB[n].keyframe_insert('rotation_quaternion', frame=i + 1)
    PB[HIPS].keyframe_insert('location', frame=i + 1)
    frame_metrics.append({'f': i + 1})

# linear interpolation
def all_fcurves(a):
    if hasattr(a, 'fcurves'):
        return list(a.fcurves)
    out = []
    for layer in a.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out
FC = all_fcurves(newact)
for fc in FC:
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
log('baked', len(FC), 'fcurves')

# ---------- measure / ground fix ----------
import numpy as np
dg = bpy.context.evaluated_depsgraph_get()
def frame_bounds(f):
    sc.frame_set(f)
    dg.update()
    lo = 1e9
    for ob in MESHES:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(n, 3)
        M = np.array(ev.matrix_world)
        w = co @ M[:3, :3].T + M[:3, 3]
        lo = min(lo, float(w[:, 2].min()))
        ev.to_mesh_clear()
    return lo

# ground pass: shift hips per frame so the lowest skinned vertex sits on GROUND
armR = arm.matrix_world.to_3x3()
minz = []
for i in range(N):
    sc.frame_set(i + 1)
    z = frame_bounds(i + 1)
    minz.append(z)
    need = GROUND - z
    if need < 0 and GROUND_PUSH != '1':
        need = 0.0
    if abs(need) > 1e-6:
        pb = PB[HIPS]
        bl = pb.matrix_basis.copy()
        rel = pb.matrix.to_3x3() @ bl.to_3x3().inverted()
        b_local = (armR @ rel).inverted() @ Vector((0, 0, need))
        bl.translation = bl.translation + b_local
        pb.matrix_basis = bl
        pb.keyframe_insert('location', frame=i + 1)
for fc in FC:
    fc.update()
for i in range(N):
    frame_metrics[i]['minz_before'] = round(minz[i], 6)
log('minz before fix', round(min(minz), 5), round(max(minz), 5))
minz2 = []
for i in range(N):
    minz2.append(frame_bounds(i + 1))
    frame_metrics[i]['minz_after'] = round(minz2[-1], 6)
    frame_metrics[i]['minz'] = round(minz2[-1], 6)
log('minz after fix', round(min(minz2), 5), round(max(minz2), 5))

# gait metrics from the baked pose
def bone_dir(n):
    return (arm.matrix_world @ PB[n].matrix).to_3x3() @ Vector((0, 1, 0))
gait = []
for i in range(N):
    sc.frame_set(i + 1)
    row = {'f': i + 1}
    for side in ('Left', 'Right'):
        up = bone_dir('mixamorig:%sUpLeg' % side)
        lo = bone_dir('mixamorig:%sLeg' % side)
        row['flex' + side[0]] = round(math.degrees(up.angle(lo)), 2)
        row['ank' + side[0]] = [round(v, 4) for v in (arm.matrix_world @ PB['mixamorig:%sFoot' % side].matrix).to_translation()]
    row['hips'] = [round(v, 4) for v in (arm.matrix_world @ PB[HIPS].matrix).to_translation()]
    gait.append(row)
flexL = [g['flexL'] for g in gait]
flexR = [g['flexR'] for g in gait]
hy = [g['hips'][2] for g in gait]
log('knee flex L', min(flexL), max(flexL), 'R', min(flexR), max(flexR))
log('hips height range', round(min(hy), 4), round(max(hy), 4), 'bob', round(max(hy) - min(hy), 4))

sc.frame_start, sc.frame_end = 1, N
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
log('saved blend', OUT_BLEND)

# ---------- drop the imported source rig so it cannot leak into the export ----------
for o in new:
    try:
        bpy.data.objects.remove(o, do_unlink=True)
    except Exception as e:
        log('remove src obj failed', o.name, e)
for a in list(bpy.data.actions):
    if a.name not in tuple(KEEP_ACTIONS + [CLIP]):
        try:
            bpy.data.actions.remove(a)
        except Exception:
            pass
log('actions kept', [a.name for a in bpy.data.actions])

# ---------- export ----------
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
if arm.animation_data is None:
    arm.animation_data_create()
arm.animation_data.action = bpy.data.actions.get('Idle_Lively')
for a in bpy.data.actions:
    a.use_fake_user = True
kw = dict(COMMON); kw['export_animations'] = True
bpy.ops.export_scene.gltf(filepath=OUT_GLB, **kw)
log('exported', OUT_GLB, os.path.getsize(OUT_GLB))

json.dump({'src': SRC, 'clip': CLIP, 'frames': N, 'dur': round(dur, 6),
           'mapped': len(MAP), 'unmapped_dst': UNMAPPED_DST, 'unmapped_src': UNMAPPED_SRC,
           'leg_ratio': round(leg_ratio, 4), 'stride_scale': round(STRIDE_SCALE, 4),
           'knee_limit': KNEE_LIMIT, 'ground_push': GROUND_PUSH,
           'minz': [round(x, 5) for x in minz], 'minz_final': [round(x, 5) for x in minz2],
           'knee_flex': {'L': [min(flexL), max(flexL)], 'R': [min(flexR), max(flexR)]},
           'hips_bob': round(max(hy) - min(hy), 4), 'gait': gait,
           'frames_meta': frame_metrics,
           'glb_bytes': os.path.getsize(OUT_GLB), 'blend': OUT_BLEND, 'glb': OUT_GLB},
          open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
log('report', REPORT)
