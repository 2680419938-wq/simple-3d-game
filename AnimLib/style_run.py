# -*- coding: utf-8 -*-
"""把已烘焙的 Run 调成「低重心猎食冲刺」：
blender -b --python style_run.py -- --glb in.glb --out out.glb [--lean 25] [--elbow 20] [--head 8]
在骨架空间里按世界 X 轴（左右轴）绕骨骼头部做附加旋转，父骨先转、子骨自动跟随。
"""
import bpy, sys, os
from mathutils import Matrix, Vector

def args():
    a = sys.argv[sys.argv.index('--')+1:]
    d = {'lean': '25', 'elbow': '20', 'head': '8', 'spine': 'Waist_033,Spine01_034,Spine02_035'}
    i = 0
    while i < len(a):
        d[a[i].lstrip('-')] = a[i+1]; i += 2
    return d

A = args()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=A['glb'])
sc = bpy.context.scene
cc = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
act = [a for a in bpy.data.actions if a.name.lower() == 'run'][0]
cc.animation_data_create(); cc.animation_data.action = act
try:
    if len(act.slots): cc.animation_data.action_slot = act.slots[0]
except Exception:
    pass

lean = float(A['lean']); elbow = float(A['elbow']); head = float(A['head'])
spine = ['CC_Base_' + n for n in A['spine'].split(',')]
# 前倾角按脊柱段分配（下段少、上段多），合计约 lean
dist = [0.34, 0.33, 0.33]
neck = ['CC_Base_NeckTwist01_036']
headb = ['CC_Base_Head_038']

def rot_about(pb, axis, deg):
    h = pb.matrix.translation.copy()
    W = Matrix.Rotation(deg * 3.14159265 / 180.0, 4, axis)
    pb.matrix = Matrix.Translation(h) @ W @ Matrix.Translation(-h) @ pb.matrix

f0, f1 = [int(round(x)) for x in act.frame_range]
def keyed(pb):
    pb.rotation_mode = 'QUATERNION'
    pb.keyframe_insert('rotation_quaternion', frame=f)

for f in range(f0, f1 + 1):
    sc.frame_set(f)
    for i, nm in enumerate(spine):
        pb = cc.pose.bones.get(nm)
        if not pb: continue
        rot_about(pb, 'X', lean * dist[i])
        bpy.context.view_layer.update()
        keyed(pb)
    for nm in neck:
        pb = cc.pose.bones.get(nm)
        if pb:
            rot_about(pb, 'X', head * 0.4); bpy.context.view_layer.update(); keyed(pb)
    for nm in headb:
        pb = cc.pose.bones.get(nm)
        if pb:
            rot_about(pb, 'X', head * 0.6); bpy.context.view_layer.update(); keyed(pb)
    # 肘部再收紧：前臂绕世界 X 轴反向转（手朝前）
    for nm in ('CC_Base_L_Forearm_051', 'CC_Base_R_Forearm_076'):
        pb = cc.pose.bones.get(nm)
        if pb:
            rot_about(pb, 'X', -elbow); bpy.context.view_layer.update(); keyed(pb)

cc.animation_data.action = None
# 保留 Idle/Walk 等其他动作
bpy.ops.export_scene.gltf(filepath=A['out'], export_format='GLB', export_image_format='WEBP',
    export_image_quality=80, export_animations=True, export_animation_mode='ACTIONS',
    export_apply=False, export_yup=True)
print('EXPORTED', A['out'], os.path.getsize(A['out']), 'lean', lean, 'elbow', elbow)