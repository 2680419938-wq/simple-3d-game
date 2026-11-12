# walkgen_world.py -- procedural walk authored directly in world space (fore/aft swing about X, arms down)
import bpy, sys, json, math
from mathutils import Matrix, Vector, Quaternion
a = sys.argv[sys.argv.index('--')+1:]
O = {}
i=0
while i<len(a):
    if a[i].startswith('--'):
        k=a[i].lstrip('-'); v=a[i+1] if i+1<len(a) and not a[i+1].startswith('--') else '1'
        O[k]=v; i+=2 if (i+1<len(a) and not a[i+1].startswith('--')) else 1
    else: i+=1
SRC, OUTB = O['src'], O['out-blend']
GLB = O.get('out-glb')
NF = int(O.get('frames','33'))
SWING = float(O.get('swing','24'))     # deg thigh fore/aft amplitude
KNEE  = float(O.get('knee','38'))      # deg extra knee bend at peak
ARMDN = float(O.get('armdn','62'))     # deg arms lowered from T
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
rig = bpy.data.objects.get('DragonMan_Rig')
Wm = arm.matrix_world
sc = bpy.context.scene
sc.render.fps = 30

arm.data.pose_position = 'REST'
bpy.context.view_layer.update()
R0 = {}
H0 = {}
for b in arm.pose.bones:
    R0[b.name] = b.matrix.to_3x3().normalized()
    H0[b.name] = b.matrix.translation.copy()

X = Vector((1,0,0)); Y = Vector((0,1,0)); Z = Vector((0,0,1))
def rx(deg): return Matrix.Rotation(math.radians(deg), 3, 'X')

def set_world_rot(name, rot3):
    pb = arm.pose.bones[name]
    pb.matrix = Matrix.Translation(pb.matrix.translation) @ rot3.to_4x4()
    bpy.context.view_layer.update()

def pose_frame(t, dz):
    p = 2*math.pi*t
    # hips: bob + slight pitch
    hips = arm.pose.bones['mixamorig:Hips']
    bob = 0.012*math.cos(2*p) + dz
    rotH = rx(4.0) @ R0['mixamorig:Hips']
    hips.matrix = Matrix.Translation(H0['mixamorig:Hips'] + Vector((0,0,bob))) @ rotH.to_4x4()
    bpy.context.view_layer.update()
    for s, ph in (('Left', 0.0), ('Right', math.pi)):
        th = SWING*math.sin(p+ph)                  # + = forward (-Y)
        knee = max(0.0, KNEE*math.sin(p+ph+2.2)) + 6.0
        set_world_rot('mixamorig:%sUpLeg'%s, rx(th) @ R0['mixamorig:%sUpLeg'%s])
        set_world_rot('mixamorig:%sLeg'%s,  rx(th - knee) @ R0['mixamorig:%sLeg'%s])
        fa = max(-20.0, min(20.0, 0.45*(th - knee)))
        set_world_rot('mixamorig:%sFoot'%s, rx(fa) @ R0['mixamorig:%sFoot'%s])
        for tb in ('%sToeBase','%sToeEnd','%sToe02End','%sToe02End.001','%sToe03Base','%sToe03End'):
            nm = 'mixamorig:' + (tb % s)
            if nm in R0: set_world_rot(nm, rx(fa) @ R0[nm])
    # arms: lower + counter swing
    for s, sgn, ph in (('Left', 1.0, math.pi), ('Right', -1.0, 0.0)):
        up = 'mixamorig:%sArm' % s
        rest_dir = (R0[up] @ Vector((0,1,0))).normalized()   # bone Y axis == bone direction
        a_sw = 12.0*math.sin(p+ph)
        tgt = (Quaternion(Z, math.radians(-ARMDN*sgn)) @ Quaternion(X, math.radians(a_sw)) @ rest_dir).normalized()
        q = rest_dir.rotation_difference(tgt)
        set_world_rot(up, q.to_matrix() @ R0[up])
        fo = 'mixamorig:%sForeArm' % s
        rfd = (R0[fo] @ Vector((0,1,0))).normalized()
        tf = (Quaternion(Z, math.radians(-ARMDN*sgn)) @ Quaternion(X, math.radians(a_sw+18.0)) @ rfd).normalized()
        qf = rfd.rotation_difference(tf)
        set_world_rot(fo, qf.to_matrix() @ R0[fo])
        hd = 'mixamorig:%sHand' % s
        set_world_rot(hd, qf.to_matrix() @ R0[hd])

meshes = [bpy.data.objects[n] for n in ('DragonMan_Body','DragonMan_Foot.L','DragonMan_Foot.R')]
def minz():
    m = 1e9
    for ob in meshes:
        obe = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = obe.to_mesh()
        M = ob.matrix_world
        for v in me.vertices:
            z = (M @ v.co).z
            if z < m: m = z
        obe.to_mesh_clear()
    return m

old = bpy.data.actions.get('Walk')
if old: bpy.data.actions.remove(old)
arm.animation_data_create()
arm.animation_data.action = None
act = None
KEY = ['mixamorig:Hips'] + ['mixamorig:%s%s'%(s,b) for s in ('Left','Right') for b in ('UpLeg','Leg','Foot','ToeBase','ToeEnd','Toe02End','Toe02End.001','Toe03Base','Toe03End')] \
      + ['mixamorig:%s%s'%(s,b) for s in ('Left','Right') for b in ('Arm','ForeArm','Hand')]
rows = []
for i in range(NF):
    t = i/(NF-1)
    pose_frame(t, 0.0)
    dz = -minz()
    pose_frame(t, dz)
    for nm in KEY:
        pb = arm.pose.bones.get(nm)
        if not pb: continue
        pb.keyframe_insert('rotation_quaternion', frame=i+1)
        pb.keyframe_insert('location', frame=i+1)
    rows.append({'f': i+1, 'dz': round(dz,4), 'minz': round(minz(),5)})
act = arm.animation_data.action
act.name = 'Walk'
def all_fcurves(a):
    if hasattr(a, 'fcurves'): return list(a.fcurves)
    out = []
    for layer in a.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out
for fc in all_fcurves(act):
    for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
print('[WG] minz range', min(r['minz'] for r in rows), max(r['minz'] for r in rows), 'dz', round(min(r['dz'] for r in rows),3), round(max(r['dz'] for r in rows),3))
arm.data.pose_position = 'POSE'
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[WG] saved', OUTB)
