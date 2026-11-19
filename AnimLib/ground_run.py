# -*- coding: utf-8 -*-
"""逐帧贴地修正（只抬升、不下压），保持原有起伏与腾空相。
blender -b --python ground_run.py -- --glb in.glb --out out.glb [--target 0.005] [--smooth 2]
"""
import bpy, sys, os
from mathutils import Vector

def args():
    a = sys.argv[sys.argv.index('--')+1:]
    d = {'target': '0.005', 'smooth': '2'}
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
if len(act.slots): cc.animation_data.action_slot = act.slots[0]
target = float(A['target']); sm = int(A['smooth'])
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() is cc]
pbh = cc.pose.bones['CC_Base_Hip_02']
f0, f1 = [int(round(x)) for x in act.frame_range]

def minz():
    mn = 1e9
    dg = bpy.context.evaluated_depsgraph_get()
    for o in meshes:
        ev = o.evaluated_get(dg); me = ev.to_mesh(); mw = o.matrix_world
        for v in me.vertices:
            z = (mw @ v.co).z
            if z < mn: mn = z
        ev.to_mesh_clear()
    return mn

raw = []
for f in range(f0, f1 + 1):
    sc.frame_set(f)
    raw.append(minz())
print('RAW', ' '.join('%.3f' % v for v in raw))
need = [max(0.0, target - v) for v in raw]
# 平滑：先做窗口最大值膨胀，再做均值，保证抬升量足够且过渡连续
for _ in range(2):
    need = [max(need[max(0, i-1):min(len(need), i+2)]) for i in range(len(need))]
off = []
n = len(need)
for i in range(n):
    lo, hi = max(0, i - sm), min(n, i + sm + 1)
    off.append(sum(need[lo:hi]) / (hi - lo))
print('OFFSET', ' '.join('%.3f' % v for v in off))
locs = []
for f in range(f0, f1 + 1):
    sc.frame_set(f)
    locs.append(pbh.location.copy())
axis = cc.data.bones['CC_Base_Hip_02'].matrix_local.to_3x3().inverted()
for i, f in enumerate(range(f0, f1 + 1)):
    sc.frame_set(f)
    pbh.location = locs[i] + (axis @ Vector((0, 0, off[i])))
    pbh.keyframe_insert('location', frame=f)
sc.frame_set(f0)
print('NEWMIN', ' '.join('%.3f' % (raw[i] + off[i]) for i in range(n)))
cc.animation_data.action = None
bpy.ops.export_scene.gltf(filepath=A['out'], export_format='GLB', export_image_format='WEBP',
    export_image_quality=80, export_animations=True, export_animation_mode='ACTIONS',
    export_apply=False, export_yup=True)
print('EXPORTED', A['out'], os.path.getsize(A['out']))
