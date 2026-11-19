
# -*- coding: utf-8 -*-
"""Mixamo FBX -> CC_Base 骨架重定向。用法：
blender -b --python mixamo_retarget.py -- --glb <alien.glb> --fbx run.fbx[:Name] --out <out.glb> [--dry]
"""
import bpy, sys, os
from mathutils import Matrix, Vector

def args():
    a = sys.argv[sys.argv.index('--')+1:]
    d = {'dry': False, 'fbx': [], 'inplace': False, 'neutral': True, 'lift': '0'}
    i = 0
    while i < len(a):
        k = a[i]
        if k == '--dry':
            d['dry'] = True; i += 1; continue
        if k == '--inplace':
            d['inplace'] = True; i += 1; continue
        if k == '--no-neutral':
            d['neutral'] = False; i += 1; continue
        v = a[i+1] if i+1 < len(a) else ''
        if k == '--fbx':
            d['fbx'].append(v)
        else:
            d[k.lstrip('-')] = v
        i += 2
    return d

M = {
 'Hips':'CC_Base_Hip_02','Spine':'CC_Base_Waist_033','Spine1':'CC_Base_Spine01_034','Spine2':'CC_Base_Spine02_035',
 'Neck':'CC_Base_NeckTwist01_036','Head':'CC_Base_Head_038','Jaw':'CC_Base_JawRoot_040',
 'LeftShoulder':'CC_Base_L_Clavicle_049','LeftArm':'CC_Base_L_Upperarm_050','LeftForeArm':'CC_Base_L_Forearm_051','LeftHand':'CC_Base_L_Hand_055',
 'RightShoulder':'CC_Base_R_Clavicle_074','RightArm':'CC_Base_R_Upperarm_075','RightForeArm':'CC_Base_R_Forearm_076','RightHand':'CC_Base_R_Hand_080',
 'LeftUpLeg':'CC_Base_L_Thigh_04','LeftLeg':'CC_Base_L_Calf_05','LeftFoot':'CC_Base_L_Foot_06','LeftToeBase':'CC_Base_L_ToeBase_08',
 'RightUpLeg':'CC_Base_R_Thigh_00','RightLeg':'CC_Base_R_Calf_019','RightFoot':'CC_Base_R_Foot_021','RightToeBase':'CC_Base_R_ToeBase_022',
}
# 手指：模型只有 4 指（Index / Mid / Pinky / Thumb），Mixamo 的 Ring 无处可落，丢弃
for s, p in (('Left','L'), ('Right','R')):
    for f_mix, f_cc in (('Thumb','Thumb'), ('Index','Index'), ('Middle','Mid'), ('Pinky','Pinky')):
        for n in (1,2,3):
            M['%sHand%s%d' % (s, f_mix, n)] = 'CC_Base_%s_%s%d_%s' % (p, f_cc, n, '')  # 稍后按实际名字补齐

def find_rig(prefix):
    for o in bpy.data.objects:
        if o.type == 'ARMATURE' and any(b.name.startswith(prefix) for b in o.data.bones):
            return o
    return None

def resolve_map(cc_rig, mix_rig):
    """把 M 里的 CC 名字（可能有空尾号）解析成真实骨骼名，输出 [(cc_bone, mix_bone)]"""
    cc = {b.name for b in cc_rig.data.bones}
    mix = {b.name: b for b in mix_rig.data.bones}
    out, miss = [], []
    for mk, ck in M.items():
        mb = None
        for cand in ('mixamorig:'+mk, 'mixamorig_'+mk, mk, 'mixamorig'+mk):
            if cand in mix: mb = mix[cand]; break
        if mb is None: miss.append(mk); continue
        if ck in cc: out.append((cc_rig.data.bones[ck], mb)); continue
        base = ck.rsplit('_', 1)[0] if ck.endswith('_') else ck
        hits = [n for n in cc if n.startswith(base) and '_scaleCompensation' not in n]
        if len(hits) == 1: out.append((cc_rig.data.bones[hits[0]], mb))
        else: miss.append('%s -> %s (cands %s)' % (mk, ck, hits[:3]))
    return out, miss

def bone_depth(b):
    d = 0
    while b.parent: d += 1; b = b.parent
    return d

A_LIFT = ['0']
# 中立帧归一化：源绑定（Mixamo T-pose）与目标绑定（异形 A-pose）不同，直接搬世界旋转会把
# 「T->A 放下手臂」这段静态差当成动画逐帧施加（实测上臂恒定偏 68°，两手在身后交叉）。
# 以源动作第一帧为中立帧，把它的偏差除掉，只保留相对中立帧的运动。
A_NEUTRAL = [True]

def retarget(cc_rig, mix_rig, pairs, action, name, hip_pairs, inplace=False):
    sc = bpy.context.scene
    mw_m = mix_rig.matrix_world.copy(); mw_c = cc_rig.matrix_world.copy()
    mw_mi = mw_m.inverted(); mw_ci = mw_c.inverted()
    s = (mw_c @ cc_rig.data.bones[pairs[0][0].name].matrix_local.translation).length
    mm = (mw_m @ mix_rig.data.bones[pairs[0][1].name].matrix_local.translation).length
    ratio = s / mm if mm > 1e-6 else 1.0

    mix_rig.animation_data_create(); mix_rig.animation_data.action = action
    cc_rig.animation_data_create()
    act = bpy.data.actions.new(name); act.use_fake_user = True
    cc_rig.animation_data.action = act
    for pb in cc_rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'; pb.matrix_basis = Matrix.Identity(4)

    f0, f1 = int(action.frame_range[0]), int(action.frame_range[1])
    pair_by_cc = {cb.name: mb for cb, mb in pairs}
    hip_names = {c.name for c, m in hip_pairs}
    allb = sorted(cc_rig.data.bones, key=bone_depth)
    I4 = Matrix.Identity(4)
    DN, TWN = {}, {}
    if A_NEUTRAL[0]:
        sc.frame_set(f0)
        for cb in allb:
            mb = pair_by_cc.get(cb.name)
            if mb is None: continue
            P_m0 = mw_m @ mix_rig.pose.bones[mb.name].matrix
            base = mw_m @ mb.matrix_local
            DN[mb.name] = (P_m0 @ base.inverted()).inverted()
            TWN[mb.name] = P_m0.translation - base.translation
        print('NEUTRAL f0=%d bones=%d' % (f0, len(DN)))
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        P = {}
        for cb in allb:
            R_c = cb.matrix_local
            ref = (P[cb.parent.name] @ cb.parent.matrix_local.inverted() @ R_c) if cb.parent else R_c
            mb = pair_by_cc.get(cb.name)
            if mb is None:
                B = I4
                P[cb.name] = ref
            else:
                P_m = mw_m @ mix_rig.pose.bones[mb.name].matrix
                D = P_m @ (mw_m @ mb.matrix_local).inverted()
                if mb.name in DN:  # 只保留相对中立帧的运动
                    D = D @ DN[mb.name]
                target = (mw_ci @ D @ mw_c) @ R_c
                if cb.name in hip_names:
                    t_w = P_m.translation - (mw_m @ mb.matrix_local).translation
                    if mb.name in TWN: t_w = t_w - TWN[mb.name]
                    if inplace:  # 取消根位移（前进方向 = -Y），只保留垂直起伏
                        t_w.y = 0.0
                    t_w.z += float(A_LIFT[0])
                    target.translation = R_c.translation + (mw_ci.to_3x3() @ t_w) * ratio
                B = ref.inverted() @ target
                P[cb.name] = target
            loc, rot, sca = B.decompose()
            pbc = cc_rig.pose.bones[cb.name]
            pbc.rotation_quaternion = rot
            if cb.name in hip_names:
                pbc.location = loc
                pbc.keyframe_insert('location', frame=f)
            if mb is not None:
                pbc.keyframe_insert('rotation_quaternion', frame=f)
    return act, f0, f1

def ground_fix(cc, action, f0, f1, target, meshes):
    """按整段最低点整体上抬髋部，保证不穿地且保留原有垂直起伏。"""
    cc.animation_data.action = action
    pbh = cc.pose.bones['CC_Base_Hip_02']
    sc = bpy.context.scene
    mn = 1e9
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for o in meshes:
            ev = o.evaluated_get(dg); me = ev.to_mesh(); mw = o.matrix_world
            for v in me.vertices:
                z = (mw @ v.co).z
                if z < mn: mn = z
            ev.to_mesh_clear()
    dz = target - mn
    print('GROUND min=%.4f lift=%.4f' % (mn, dz))
    if abs(dz) < 1e-4: return
    a_loc = cc.data.bones['CC_Base_Hip_02'].matrix_local.to_3x3().inverted() @ Vector((0, 0, dz))
    locs = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        locs.append(pbh.location.copy())
    for i, f in enumerate(range(f0, f1 + 1)):
        sc.frame_set(f)
        pbh.location = locs[i] + a_loc
        pbh.keyframe_insert('location', frame=f)

def main():
    A = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    # 先导入 FBX：FBX 导入器会把场景 fps 改成动画原生 fps（Mixamo 多为 60），
    # 之后所有 glTF 导入与导出都沿用这个时基，动画时长才不会翻倍或减半
    mix_rigs, acts = [], []
    for spec in A['fbx']:
        path, _, nm = spec.partition('::')
        before = set(bpy.data.actions)
        if path.lower().endswith(('.glb', '.gltf')):
            bpy.ops.import_scene.gltf(filepath=path)
        else:
            bpy.ops.import_scene.fbx(filepath=path)
        rig = find_rig('mixamorig')
        if rig is None:
            cand = [o for o in bpy.data.objects if o.type == 'ARMATURE' and o not in mix_rigs]
            rig = cand[-1] if cand else None
        new = [a for a in bpy.data.actions if a not in before]
        print('MIX RIG', rig.name if rig else None, 'FPS', sc.render.fps,
              'ACTIONS', [(a.name, tuple(round(x, 1) for x in a.frame_range)) for a in new])
        mix_rigs.append(rig)
        acts.append((rig, new, nm or os.path.splitext(os.path.basename(path))[0]))

    fps = sc.render.fps / (sc.render.fps_base or 1.0)
    bpy.ops.import_scene.gltf(filepath=A['glb'])
    cc = find_rig('CC_Base_')
    print('CC RIG', cc.name, len(cc.data.bones), 'FPS', sc.render.fps)
    for a in bpy.data.actions:
        print('  ACT %-40s %s' % (a.name, tuple(round(x, 1) for x in a.frame_range)))

    pairs, miss = resolve_map(cc, mix_rigs[0])
    print('PAIRS', len(pairs), 'MISS', miss[:10])
    if A['dry']:
        for cb, mb in sorted(pairs, key=lambda p: bone_depth(p[0])):
            print('  %-28s <- %s' % (cb.name, mb.name))
        return
    A_LIFT[0] = A.get('lift', '0')
    A_NEUTRAL[0] = A['neutral']
    hip_pairs = [(cb, mb) for cb, mb in pairs if cb.name == 'CC_Base_Hip_02']
    for rig, actlist, nm in acts:
        for a in actlist:
            out, f0, f1 = retarget(cc, rig, pairs, a, nm, hip_pairs, A['inplace'])
            print('BAKED %-12s frames %d..%d  slots %d' % (nm, f0, f1, len(out.slots)))
    if A.get('ground') is not None:
        gmesh = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() is cc]
        for a in bpy.data.actions:
            if a.name.lower() != 'run': continue
            fr = [int(round(x)) for x in a.frame_range]
            ground_fix(cc, a, fr[0], fr[1], float(A['ground']), gmesh)

    for a in list(bpy.data.actions):
        if 'mixamo' in a.name or a.name.startswith('Armature|'):
            bpy.data.actions.remove(a)
    for o in list(bpy.data.objects):
        if o.type == 'ARMATURE' and o is not cc:
            bpy.data.objects.remove(o, do_unlink=True)
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.find_armature() is not cc:
            bpy.data.objects.remove(o, do_unlink=True)
    cc.animation_data.action = None
    sc.render.fps = int(round(fps))
    sc.render.fps_base = 1.0
    print('FPS at export', sc.render.fps)
    bpy.ops.export_scene.gltf(filepath=A['out'], export_format='GLB', export_image_format='WEBP',
        export_image_quality=80, export_animations=True, export_animation_mode='ACTIONS',
        export_apply=False, export_yup=True)
    print('EXPORTED', A['out'], os.path.getsize(A['out']))

main()