# -*- coding: utf-8 -*-
# m3: build the A-Pose deliverable from the T-Pose blend (arms 45 deg down, no animation).
import bpy, sys, json, math, os
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = {argv[i].lstrip('-'): argv[i + 1] for i in range(0, len(argv) - 1, 2)}
SRC = opt['src']; DST = opt['dst']; REPORT = opt['report']
ANG = math.radians(float(opt.get('ang', 45)))

bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('WGT_')]
R = {'src': SRC, 'dst': DST, 'ang_deg': math.degrees(ANG), 'meshes': [o.name for o in meshes]}

def bbox():
    dg = bpy.context.evaluated_depsgraph_get(); lo = [9e9] * 3; hi = [-9e9] * 3
    for o in meshes:
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        for v in me.vertices:
            w = ev.matrix_world @ v.co
            for k in range(3):
                lo[k] = min(lo[k], w[k]); hi[k] = max(hi[k], w[k])
        ev.to_mesh_clear()
    return [round(v, 5) for v in lo], [round(v, 5) for v in hi]

def bone_dir(nm):
    pb = arm.pose.bones[nm]; MW = arm.matrix_world
    return ((MW @ pb.tail) - (MW @ pb.head)).normalized()

def ankle_z():
    MW = arm.matrix_world
    return {s: float((MW @ arm.pose.bones['mixamorig:%sFoot' % s].head).z) for s in ('Left', 'Right')}

R['bbox_rest'] = bbox(); R['ankle_z_rest'] = ankle_z()
R['arm_dir_rest'] = {s: [round(float(v), 5) for v in bone_dir('mixamorig:%sArm' % s)] for s in ('Left', 'Right')}
print('[M3] rest bbox', R['bbox_rest'], 'ankle', R['ankle_z_rest'])

if arm.animation_data:
    arm.animation_data_clear()
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
    pb.rotation_mode = 'QUATERNION'
bpy.context.view_layer.update()

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')
DOWN = Vector((0, 0, -1))
for nm in ('mixamorig:LeftArm', 'mixamorig:RightArm'):
    pb = arm.pose.bones[nm]; head = pb.matrix.translation.copy()
    d = (pb.tail - pb.head).normalized()
    tgt = (d * math.cos(ANG) + DOWN * math.sin(ANG)).normalized()
    q = d.rotation_difference(tgt)
    pb.matrix = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head) @ pb.matrix
    bpy.context.view_layer.update()
    R.setdefault('arm_target', {})[nm] = {'from': [round(float(v), 5) for v in d], 'to': [round(float(v), 5) for v in tgt]}
bpy.ops.object.mode_set(mode='OBJECT')
R['arm_dir_posed'] = {s: [round(float(v), 5) for v in bone_dir('mixamorig:%sArm' % s)] for s in ('Left', 'Right')}
R['arm_deg_from_vertical'] = {}
for s in ('Left', 'Right'):
    d = Vector(R['arm_dir_posed'][s])
    R['arm_deg_from_vertical'][s] = round(math.degrees(math.acos(max(-1.0, min(1.0, abs(d.z))))), 3)
print('[M3] arm dirs', R['arm_dir_posed'], 'deg from vertical', R['arm_deg_from_vertical'])

counts0 = {o.name: [len(o.data.vertices), len(o.data.polygons)] for o in meshes}
for o in meshes:
    bpy.context.view_layer.objects.active = o
    for mod in list(o.modifiers):
        if mod.type == 'ARMATURE':
            bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE'); bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.armature_apply(selected=True)
bpy.ops.object.mode_set(mode='OBJECT')
for o in meshes:
    m = o.modifiers.new('Armature', 'ARMATURE'); m.object = arm
counts1 = {o.name: [len(o.data.vertices), len(o.data.polygons)] for o in meshes}
R['counts_before'] = counts0; R['counts_after'] = counts1
assert counts0 == counts1, (counts0, counts1)
R['bbox_final'] = bbox(); R['ankle_z_final'] = ankle_z()
R['actions'] = [a.name for a in bpy.data.actions]
R['anim'] = bool(arm.animation_data and arm.animation_data.action)
R['bones'] = len(arm.data.bones); R['deform'] = sum(1 for b in arm.data.bones if b.use_deform)
print('[M3] final bbox', R['bbox_final'], 'ankle', R['ankle_z_final'], 'anim', R['anim'])
bpy.ops.wm.save_as_mainfile(filepath=DST)
json.dump(R, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[M3] saved', DST)
print('[M3] DONE')
