# -*- coding: utf-8 -*-
"""干跑验收：丢进来的 Mixamo FBX 先过这一关，再决定用哪条管线。

blender -b --python AnimLib/inspect_fbx.py -- a.fbx b.fbx ...

判定项：文件版本（Blender 只吃 7100+）、帧率、骨架/网格、动作时长、髋部水平漂移（原地与否）。
"""
import bpy, sys, os, struct

A = sys.argv[sys.argv.index('--') + 1:]
HIPS = ('hips',)

def version(p):
    with open(p, 'rb') as f:
        h = f.read(32)
    if h.startswith(b'Kaydara FBX Binary'):
        return struct.unpack('<I', h[23:27])[0]
    return 0   # ASCII FBX

def drift(arm, act, fps):
    arm.animation_data_create()
    arm.animation_data.action = act
    if getattr(arm.animation_data, 'action_slot', None) is None and act.slots:
        arm.animation_data.action_slot = act.slots[0]
    hip = next((b for b in arm.data.bones if b.name.lower().endswith('hips')), None)
    if not hip:
        return None
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    xs, ys = [], []
    for f in range(f0, f1 + 1, max(1, (f1 - f0) // 12 or 1)):
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        t = (arm.matrix_world @ hip.matrix_local).translation
        xs.append(t.x); ys.append(t.y)
    return round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)

for path in A:
    ver = version(path)
    name = os.path.basename(path)
    if ver and ver < 7100:
        print('FAIL %-42s FBX %d 版本过低（需要 7100+）' % (name, ver))
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        bpy.ops.import_scene.fbx(filepath=path)
    except RuntimeError as e:
        print('FAIL %-42s 导入失败：%s' % (name, e))
        continue
    sc = bpy.context.scene
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    tris = 0
    for o in meshes:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    acts = list(bpy.data.actions)
    rig = arms[0].data.bones[0].name.split(':')[0] + ':' if arms and ':' in arms[0].data.bones[0].name else '-'
    print('OK   %-42s v%d %2dfps 骨%d(%s) 网格%d(%d tri) 动作%d' % (name, ver, sc.render.fps, len(arms[0].data.bones) if arms else 0, rig, len(meshes), tris, len(acts)))
    for act in acts:
        sec = round((act.frame_range[1] - act.frame_range[0]) / sc.render.fps, 2)
        d = drift(arms[0], act, sc.render.fps) if arms else None
        tag = '原地' if d and max(d) < 0.02 else ('有根位移 %s' % (d,) if d else '?')
        print('       clip %-34s %5.2fs  %s' % (act.name, sec, tag))
