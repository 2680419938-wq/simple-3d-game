
# -*- coding: utf-8 -*-
"""往主 GLB 里追加一条 Mixamo 动作（默认 Run），保持 Idle/Walk/Jump 不变。

blender -b --python AnimLib/alien_clip_add.py -- --fbx <file.fbx> --name Run \
        --src <main.glb> --out <out.glb> [--inplace] [--lean 12] [--head 6] [--elbow 12] [--ground 0.002]

要点：
* 中立帧归一化（源 T-pose 与异形 A-pose 绑定不同，必须先除掉这段静态差）
* 源帧率按时间重采样到 24 fps，输出帧号 1..K 线性，时长 = K/24 s
* --inplace 去掉根位移的水平分量（游戏里由角色位移驱动）
* 逐帧只抬升的贴地夹紧，保留腾空相
* 风格化在骨架空间按世界 X 轴绕骨骼头部附加旋转（父骨先转）
"""
import bpy, math, os, sys
from mathutils import Matrix, Vector

def args():
    a = sys.argv[sys.argv.index('--')+1:]
    d = {'name': 'Run', 'inplace': False, 'neutral': True, 'mode': 'neutral', 'lean': '0', 'head': '0',
         'elbow': '0', 'ground': '0.002', 'fps': '24'}
    i = 0
    while i < len(a):
        k = a[i]
        if k == '--inplace': d['inplace'] = True; i += 1; continue
        if k == '--no-neutral': d['neutral'] = False; i += 1; continue
        d[k.lstrip('-')] = a[i+1]; i += 2
    return d

A = args()
M = {
 'Hips':'CC_Base_Hip_02','Spine':'CC_Base_Waist_033','Spine1':'CC_Base_Spine01_034','Spine2':'CC_Base_Spine02_035',
 'Neck':'CC_Base_NeckTwist01_036','Head':'CC_Base_Head_038','Jaw':'CC_Base_JawRoot_040',
 'LeftShoulder':'CC_Base_L_Clavicle_049','LeftArm':'CC_Base_L_Upperarm_050','LeftForeArm':'CC_Base_L_Forearm_051','LeftHand':'CC_Base_L_Hand_055',
 'RightShoulder':'CC_Base_R_Clavicle_074','RightArm':'CC_Base_R_Upperarm_075','RightForeArm':'CC_Base_R_Forearm_076','RightHand':'CC_Base_R_Hand_080',
 'LeftUpLeg':'CC_Base_L_Thigh_04','LeftLeg':'CC_Base_L_Calf_05','LeftFoot':'CC_Base_L_Foot_06','LeftToeBase':'CC_Base_L_ToeBase_08',
 'RightUpLeg':'CC_Base_R_Thigh_00','RightLeg':'CC_Base_R_Calf_019','RightFoot':'CC_Base_R_Foot_021','RightToeBase':'CC_Base_R_ToeBase_022',
}
for s, p in (('Left','L'), ('Right','R')):
    for fm, fc in (('Thumb','Thumb'), ('Index','Index'), ('Middle','Mid'), ('Pinky','Pinky')):
        for n in (1, 2, 3):
            M['%sHand%s%d' % (s, fm, n)] = 'CC_Base_%s_%s%d_' % (p, fc, n)

def find(p, ex=()):
    for o in bpy.data.objects:
        if o.type == 'ARMATURE' and o not in ex and any(b.name.startswith(p) for b in o.data.bones):
            return o

def resolve(cc, mix):
    ccb = {b.name for b in cc.data.bones}
    mixb = {b.name for b in mix.data.bones}
    out = []
    for mk, ck in M.items():
        mb = None
        for c in ('mixamorig:'+mk, 'mixamorig_'+mk, mk, 'mixamorig'+mk):
            if c in mixb: mb = mix.data.bones[c]; break
        if mb is None: continue
        if ck in ccb: out.append((cc.data.bones[ck], mb)); continue
        base = ck.rsplit('_', 1)[0] if ck.endswith('_') else ck
        h = [n for n in ccb if n.startswith(base) and '_scaleCompensation' not in n]
        if len(h) == 1: out.append((cc.data.bones[h[0]], mb))
    return out

def depth(b):
    d = 0
    while b.parent: d += 1; b = b.parent
    return d

def body_minz(meshes):
    dg = bpy.context.evaluated_depsgraph_get(); mn = 1e9
    for o in meshes:
        ev = o.evaluated_get(dg); me = ev.to_mesh(); mw = o.matrix_world
        for v in me.vertices:
            z = (mw @ v.co).z
            if z < mn: mn = z
        ev.to_mesh_clear()
    return mn

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

bpy.ops.import_scene.fbx(filepath=A['fbx'])
# 源 FBX 可能是 With Skin 下载（带蒙皮网格）：只留 mixamo 骨架，否则整套网格会被导进主 GLB
_mix0 = find('mixamorig')
for o in list(bpy.data.objects):
    if o is not _mix0: bpy.data.objects.remove(o, do_unlink=True)
srcfps = sc.render.fps / (sc.render.fps_base or 1.0)
mix = find('mixamorig')
macts = [a for a in bpy.data.actions]
mact = macts[0]
f0, f1 = int(mact.frame_range[0]), int(mact.frame_range[1])
print('FBX %s  srcfps %g  frames %d..%d  bones %d' % (os.path.basename(A['fbx']), srcfps, f0, f1, len(mix.data.bones)))

# glTF 导入按「秒 × 当前 fps」落到帧号，所以必须在导入主资产之前把场景 fps 固定成 24，
# 否则 FBX 带进来的 30 fps 会让 Idle/Walk/Jump 的帧号多出 1.25 倍、导出时整段变慢。
sc.render.fps = 24; sc.render.fps_base = 1.0
bpy.ops.import_scene.gltf(filepath=A['src'])
cc = find('CC_Base_', (mix,))
print('CC', cc.name, len(cc.data.bones), 'actions', [a.name for a in bpy.data.actions if a is not mact])
for o in list(bpy.data.objects):
    if o.name.startswith('Icosphere'): bpy.data.objects.remove(o, do_unlink=True)

pairs = resolve(cc, mix); pair_by = {cb.name: mb for cb, mb in pairs}
print('MAPPED', len(pairs))
MWM = mix.matrix_world.copy(); MWC = cc.matrix_world.copy(); MWCI = MWC.inverted()
ratio = (MWC @ cc.data.bones['CC_Base_Hip_02'].matrix_local.translation).length / \
        (MWM @ mix.data.bones['mixamorig:Hips'].matrix_local.translation).length

mix.animation_data_create(); mix.animation_data.action = mact
cc.animation_data_create()
act = bpy.data.actions.new(A['name']); act.use_fake_user = True
cc.animation_data.action = act
for pb in cc.pose.bones:
    pb.rotation_mode = 'QUATERNION'; pb.matrix_basis = Matrix.Identity(4)

allb = sorted(cc.data.bones, key=depth)
DN = {}; TWN = None
if A['mode'] == 'neutral' and A['neutral']:
    sc.frame_set(f0)
    for cb in allb:
        mb = pair_by.get(cb.name)
        if mb is None: continue
        P_m0 = MWM @ mix.pose.bones[mb.name].matrix
        DN[cb.name] = (P_m0 @ (MWM @ mb.matrix_local).inverted()).inverted()
        if cb.name == 'CC_Base_Hip_02':
            TWN = P_m0.translation - (MWM @ mb.matrix_local).translation
    print('NEUTRAL f0=%d bones=%d' % (f0, len(DN)))

K = max(2, int(round((f1 - f0 + 1) * 24.0 / srcfps)))
step = srcfps / 24.0
for k in range(K):
    sf = f0 + k * step
    sc.frame_set(int(math.floor(sf)), subframe=sf - math.floor(sf))
    P = {}
    for cb in allb:
        R_c = cb.matrix_local
        ref = (P[cb.parent.name] @ cb.parent.matrix_local.inverted() @ R_c) if cb.parent else R_c
        mb = pair_by.get(cb.name)
        if mb is None:
            P[cb.name] = ref; continue
        P_m = MWM @ mix.pose.bones[mb.name].matrix
        if A['mode'] == 'world':
            # 直接复制世界朝向。源绑定是 T-pose、目标是 A-pose，偏差式重定向会把这段
            # 静态差当成动画叠加（手臂恒低 68°）；换成复制朝向则朝向完全由源动作决定。
            Qt = MWCI.to_3x3().normalized() @ P_m.to_3x3().normalized()
            target = Qt.to_4x4(); target.translation = ref.translation
        else:
            D = P_m @ (MWM @ mb.matrix_local).inverted()
            if cb.name in DN: D = D @ DN[cb.name]
            target = (MWCI @ D @ MWC) @ R_c
        if cb.name == 'CC_Base_Hip_02':
            t_w = P_m.translation - (MWM @ mb.matrix_local).translation
            if TWN is not None: t_w = t_w - TWN
            if A['inplace']:
                t_w.x = 0.0; t_w.y = 0.0
            target.translation = R_c.translation + (MWCI.to_3x3() @ t_w) * ratio
        B = ref.inverted() @ target; P[cb.name] = target
        loc, rot, _ = B.decompose(); pc = cc.pose.bones[cb.name]
        pc.rotation_quaternion = rot
        if cb.name == 'CC_Base_Hip_02':
            pc.location = loc; pc.keyframe_insert('location', frame=k + 1)
        pc.keyframe_insert('rotation_quaternion', frame=k + 1)
print('BAKED %s frames 1..%d (%.3f s @24fps)' % (A['name'], K, K / 24.0))

for o in list(bpy.data.objects):
    if o is mix: continue
bpy.data.objects.remove(mix, do_unlink=True)
for a in list(bpy.data.actions):
    if a is not act and ('mixamo' in a.name.lower() or a.name.startswith('Armature|') or a is mact):
        print('DEL action', a.name); bpy.data.actions.remove(a)

try: cc.animation_data.action_slot = act.slots[0]
except Exception as e: print('SLOT', e)

lean = float(A['lean']); head = float(A['head']); elbow = float(A['elbow'])
def rot_about(pb, axis, deg):
    h = pb.matrix.translation.copy()
    W = Matrix.Rotation(deg * math.pi / 180.0, 4, axis)
    pb.matrix = Matrix.Translation(h) @ W @ Matrix.Translation(-h) @ pb.matrix

if lean or head or elbow:
    spine = ['CC_Base_Waist_033', 'CC_Base_Spine01_034', 'CC_Base_Spine02_035']
    dist = [0.34, 0.33, 0.33]
    for f in range(1, K + 1):
        sc.frame_set(f)
        for i, nm in enumerate(spine):
            pb = cc.pose.bones.get(nm)
            if pb:
                rot_about(pb, 'X', lean * dist[i]); bpy.context.view_layer.update()
                pb.keyframe_insert('rotation_quaternion', frame=f)
        for nm, share in (('CC_Base_NeckTwist01_036', 0.4), ('CC_Base_Head_038', 0.6)):
            pb = cc.pose.bones.get(nm)
            if pb:
                rot_about(pb, 'X', head * share); bpy.context.view_layer.update()
                pb.keyframe_insert('rotation_quaternion', frame=f)
        for nm in ('CC_Base_L_Forearm_051', 'CC_Base_R_Forearm_076'):
            pb = cc.pose.bones.get(nm)
            if pb:
                rot_about(pb, 'X', -elbow); bpy.context.view_layer.update()
                pb.keyframe_insert('rotation_quaternion', frame=f)
    print('STYLE lean %.1f head %.1f elbow %.1f' % (lean, head, elbow))

# ---- 贴地 ----
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() is cc]
hp = cc.pose.bones['CC_Base_Hip_02']
M3 = (cc.matrix_world.to_3x3() @ cc.data.bones['CC_Base_Hip_02'].matrix_local.to_3x3()).inverted()
target = float(A['ground'])

# 1) 整段整体平移：把全片最低点对齐到 target（循环动作的高低由动作本身决定，不能逐帧压平）
gmin = 1e9
for f in range(1, K + 1):
    sc.frame_set(f); gmin = min(gmin, body_minz(meshes))
off = target - gmin
if abs(off) > 1e-4:
    for f in range(1, K + 1):
        sc.frame_set(f)
        hp.location = hp.location + (M3 @ Vector((0, 0, off)))
        hp.keyframe_insert('location', frame=f)
print('SHIFT %+.4f (global min %.4f -> %.4f)' % (off, gmin, target))
lifted = 0; maxneed = 0.0
for f in range(1, K + 1):
    sc.frame_set(f)
    need = max(0.0, target - body_minz(meshes))
    maxneed = max(maxneed, need)
    if need > 1e-6:
        lifted += 1
        hp.location = hp.location + (M3 @ Vector((0, 0, need)))
        hp.keyframe_insert('location', frame=f)
print('CLAMP lifted %d/%d frames, max %.4f' % (lifted, K, maxneed))
try: cc.animation_data.action_slot = act.slots[0]
except Exception: pass
mn2 = 1e9; mnf = 0
for f in range(1, K + 1):
    sc.frame_set(f); m = body_minz(meshes)
    if m < mn2: mn2, mnf = m, f
print('POST minz %.4f at F%d' % (mn2, mnf))

sc.render.fps = 24; sc.render.fps_base = 1.0
for a in bpy.data.actions: a.use_fake_user = True
cc.animation_data.action = None
print('ACTIONS', [(a.name, tuple(round(x, 1) for x in a.frame_range)) for a in bpy.data.actions])
bpy.ops.export_scene.gltf(filepath=A['out'], export_format='GLB',
    export_image_format='WEBP', export_image_quality=80,
    export_animations=True, export_animation_mode='ACTIONS',
    export_skins=True, export_yup=True, export_apply=False,
    export_bake_animation=False, export_optimize_animation_size=False)
print('EXPORTED', A['out'], os.path.getsize(A['out']))
