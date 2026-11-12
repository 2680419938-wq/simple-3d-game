
# Build a synthetic "Mixamo-spec" humanoid (human proportions, cm units, A-pose arms)
# and bake a procedural Run cycle, then export FBX + BVH as a foreign test clip.
import bpy, math, os, sys
from mathutils import Vector, Matrix, Quaternion

OUT = r"D:\ai\建模\AnimLib\test"
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
sc.unit_settings.scale_length = 0.01          # centimetres

arm_data = bpy.data.armatures.new("SrcArmature")
arm = bpy.data.objects.new("SrcRig", arm_data)
sc.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')

# name, head, tail, parent   (metres, then scaled to cm by object scale 0.01? no: build in cm space)
def M(x, y, z): return Vector((x, y, z))
V = 100.0   # build in centimetres directly
BONES = [
 ("Hips",         M(0,0,95*V/100*0+0.95*V), None, None),
]
H = 100.0  # 1 cm unit = 1.75 m tall

spec = [
 ("Hips",        (0, 0, 0.95), (0, 0, 1.05), None),
 ("Spine",       (0, 0, 1.05), (0, 0, 1.20), "Hips"),
 ("Spine1",      (0, 0, 1.20), (0, 0, 1.35), "Spine"),
 ("Spine2",      (0, 0, 1.35), (0, 0, 1.50), "Spine1"),
 ("Neck",        (0, 0, 1.50), (0, 0, 1.60), "Spine2"),
 ("Head",        (0, 0, 1.60), (0, 0, 1.75), "Neck"),
 ("LeftShoulder",(0.03, 0, 1.47), (0.17, 0, 1.47), "Spine2"),
 ("LeftArm",     (0.17, 0, 1.47), (0.45, 0, 1.47), "LeftShoulder"),
 ("LeftForeArm", (0.45, 0, 1.47), (0.70, 0, 1.47), "LeftArm"),
 ("LeftHand",    (0.70, 0, 1.47), (0.80, 0, 1.47), "LeftForeArm"),
 ("RightShoulder",(-0.03, 0, 1.47), (-0.17, 0, 1.47), "Spine2"),
 ("RightArm",    (-0.17, 0, 1.47), (-0.45, 0, 1.47), "RightShoulder"),
 ("RightForeArm",(-0.45, 0, 1.47), (-0.70, 0, 1.47), "RightArm"),
 ("RightHand",   (-0.70, 0, 1.47), (-0.80, 0, 1.47), "RightForeArm"),
 ("LeftUpLeg",   (0.09, 0, 0.95), (0.09, 0, 0.52), "Hips"),
 ("LeftLeg",     (0.09, 0, 0.52), (0.09, 0, 0.09), "LeftUpLeg"),
 ("LeftFoot",    (0.09, 0, 0.09), (0.09, -0.12, 0.03), "LeftLeg"),
 ("LeftToeBase", (0.09, -0.12, 0.03), (0.09, -0.25, 0.03), "LeftFoot"),
 ("RightUpLeg",  (-0.09, 0, 0.95), (-0.09, 0, 0.52), "Hips"),
 ("RightLeg",    (-0.09, 0, 0.52), (-0.09, 0, 0.09), "RightUpLeg"),
 ("RightFoot",   (-0.09, 0, 0.09), (-0.09, -0.12, 0.03), "RightLeg"),
 ("RightToeBase",(-0.09, -0.12, 0.03), (-0.09, -0.25, 0.03), "RightFoot"),
]

eb = {}
for name, h, t, parent in spec:
    b = arm_data.edit_bones.new("mixamorig:" + name)
    # source rig carries a constant scale so the imported object is NOT 1:1
    b.head = Vector(h) * H
    b.tail = Vector(t) * H
    b.roll = 0.0
    eb[name] = b
for name, h, t, parent in spec:
    if parent:
        eb[name].parent = eb[parent]
        eb[name].use_connect = (Vector(h) - Vector([s[2] for s in spec if s[0]==parent][0])).length < 1e-6

bpy.ops.object.mode_set(mode='OBJECT')

# A-pose: rotate upper arms 40 deg down around Y (world), so rest differs from ours
bpy.ops.object.mode_set(mode='POSE')
for side, sign in (("Left", -1.0), ("Right", 1.0)):
    for bn in ("mixamorig:%sArm" % side, "mixamorig:%sForeArm" % side, "mixamorig:%sHand" % side):
        pb = arm.pose.bones[bn]
        pb.rotation_mode = 'QUATERNION'
        ang = math.radians(40.0) * (1.0 if sign < 0 else -1.0)
        pb.rotation_quaternion = Quaternion((0, 1, 0), ang)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()

# Bake: procedural run cycle on the SOURCE rig (local-space rotations)
arm.animation_data_create()
act = bpy.data.actions.new("SrcRun")
arm.animation_data.action = act
NF = 19

def key(pb, f):
    pb.keyframe_insert("rotation_quaternion", frame=f)

pbmap = {b.name: arm.pose.bones[b.name] for b in arm_data.bones}
for pb in pbmap.values():
    pb.rotation_mode = 'QUATERNION'

for i in range(NF):
    f = i + 1
    ph = 2.0 * math.pi * i / (NF - 1)
    for pb in pbmap.values():
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
    # legs: flex swing about local X
    swing = math.radians(38.0)
    knee = math.radians(70.0)
    for side, off in (("Left", 0.0), ("Right", math.pi)):
        s = math.sin(ph + off)
        c = math.cos(ph + off)
        pbmap["mixamorig:%sUpLeg" % side].rotation_quaternion = Quaternion((1, 0, 0), swing * s)
        kn = knee * max(0.0, -c) * 0.9 + math.radians(12.0)
        pbmap["mixamorig:%sLeg" % side].rotation_quaternion = Quaternion((1, 0, 0), kn)
        pbmap["mixamorig:%sArm" % side].rotation_quaternion = Quaternion((0, 0, 1), math.radians(62.0) * (1 if side == "Left" else -1)) @ Quaternion((1, 0, 0), -swing * 0.8 * s)
        pbmap["mixamorig:%sForeArm" % side].rotation_quaternion = Quaternion((0, 1, 0), math.radians(-70.0) * (1 if side == "Left" else -1))
    # torso lean + bob
    pbmap["mixamorig:Spine2"].rotation_quaternion = Quaternion((1, 0, 0), math.radians(-8.0))
    pbmap["mixamorig:Hips"].location = Vector((0, 0, 0.035 * H * math.cos(2 * ph)))
    for pb in pbmap.values():
        key(pb, f)
    pbmap["mixamorig:Hips"].keyframe_insert("location", frame=f)

sc.frame_start, sc.frame_end = 1, NF
def all_fcurves(a):
    if hasattr(a, "fcurves"):
        return list(a.fcurves)
    out = []
    for layer in a.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out

for fc in all_fcurves(act):
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'

os.makedirs(OUT, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.fbx(
    filepath=os.path.join(OUT, "SrcMixamoSpec_Run.fbx"),
    use_selection=True, apply_scale_options='FBX_SCALE_ALL',
    bake_anim=True, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
    bake_anim_force_startend_keying=True, add_leaf_bones=False, object_types={'ARMATURE'},
)
bpy.ops.export_anim.bvh(filepath=os.path.join(OUT, "SrcMixamoSpec_Run.bvh"),
                        frame_start=1, frame_end=NF, global_scale=100.0)
print("WROTE", os.path.join(OUT, "SrcMixamoSpec_Run.fbx"), os.path.getsize(os.path.join(OUT, "SrcMixamoSpec_Run.fbx")))
print("WROTE bvh", os.path.getsize(os.path.join(OUT, "SrcMixamoSpec_Run.bvh")))
print("SRC_BONES", len(arm_data.bones))
