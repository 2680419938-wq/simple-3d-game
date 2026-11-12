# walkgen4.py -- in-place walk: stance/swing schedule, foot flat in stance, world-space rotation axes
import bpy, sys, math
from mathutils import Matrix, Vector
a = sys.argv[sys.argv.index('--')+1:]
O = {}; i=0
while i<len(a):
    if a[i].startswith('--'):
        k=a[i].lstrip('-'); v=a[i+1] if i+1<len(a) and not a[i+1].startswith('--') else '1'
        O[k]=v; i+=2 if (i+1<len(a) and not a[i+1].startswith('--')) else 1
    else: i+=1
SRC, OUTB = O['src'], O['out-blend']
NF = int(O.get('frames','33'))
TH = float(O.get('thigh','27')); KNEE = float(O.get('knee','48')); ARMDN = float(O.get('armdn','62'))
ARMSW = float(O.get('armsw','12')); DUTY = float(O.get('duty','0.62')); BOB = float(O.get('bob','0.012'))
ELBOW = float(O.get('elbow','20')); TAILS = float(O.get('tailsway','4.5'))
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']; arm.data.pose_position='POSE'
sc = bpy.context.scene; sc.render.fps = 30
M3 = arm.matrix_world.to_3x3(); M3i = M3.inverted()
arm.animation_data_create()
for nm in ('Walk',):
    ex = bpy.data.actions.get(nm)
    if ex: bpy.data.actions.remove(ex)

def all_fcurves(x):
    if hasattr(x,'fcurves'): return list(x.fcurves)
    out=[]
    for layer in x.layers:
        for strip in layer.strips:
            for cb in strip.channelbags: out.extend(cb.fcurves)
    return out

REL = {}
for b in arm.data.bones:
    REL[b.name] = (b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent else b.matrix_local.copy()
M0 = {}
for b in arm.data.bones:
    M0[b.name] = (M0[b.parent.name] @ REL[b.name]) if b.parent else REL[b.name].copy()

def Rw(axis, deg): return Matrix.Rotation(math.radians(deg), 3, axis)
P = {}
def limb(nm, Rext):
    par = arm.data.bones[nm].parent
    parname = par.name if par else None
    base = P.get(parname, M0.get(parname, Matrix())) if parname else Matrix()
    head = (base @ REL[nm]).translation
    R = M3i @ Rext @ M3 @ M0[nm].to_3x3()
    return Matrix.Translation(head) @ R.to_4x4()

def leg_state(u):
    if u < 0.0: u += 1.0
    if u < DUTY:
        w = u / DUTY
        s = -1.0 + 2.0*w
        knee = 5.0 + 7.0*math.sin(math.pi*w)
        fa = 0.0
        lift = 0.0
    else:
        v = (u - DUTY) / (1.0 - DUTY)
        e = v*v*(3-2*v)
        s = 1.0 - 2.0*e
        knee = 5.0 + KNEE*math.sin(math.pi*v)**0.8
        fa = -12.0*math.sin(math.pi*v)
        lift = math.sin(math.pi*v)
    return s, knee, fa, lift

def build_pose(t):
    P.clear()
    p = 2*math.pi*t
    P['mixamorig:Root'] = M0['mixamorig:Root'].copy()
    bob = BOB*(0.5 - 0.5*math.cos(2*p)) - 0.5*BOB
    hips_head = M0['mixamorig:Hips'].translation + Vector((0,0,bob))
    P['mixamorig:Hips'] = Matrix.Translation(hips_head) @ (M3i @ Rw('X',4.0) @ M3 @ M0['mixamorig:Hips'].to_3x3()).to_4x4()
    for sname, ph, sgn in (('Left',0.0,1.0), ('Right',0.5,-1.0)):
        s, knee, fa, lift = leg_state((t + ph) % 1.0)
        th = TH*s
        for bn, deg in (('UpLeg',th),('Leg',th-knee),('Foot',fa),('ToeBase',fa),('ToeEnd',fa),
                        ('Toe02End',fa),('Toe02End.001',fa),('Toe03Base',fa),('Toe03End',fa)):
            nm = 'mixamorig:%s%s' % (sname, bn)
            if nm not in M0: continue
            P[nm] = limb(nm, Rw('X', deg))
        sw = ARMSW*math.sin(2*math.pi*(t + ph + 0.5))
        for bn, extra in (('Arm',0.0),('ForeArm',ELBOW),('Hand',ELBOW)):
            nm = 'mixamorig:%s%s' % (sname, bn)
            if nm not in M0: continue
            P[nm] = limb(nm, Rw('X', sw+extra) @ Rw('Y', ARMDN*sgn))
    for i in range(1,7):
        nm = 'mixamorig:tail.%03d' % i
        if nm not in M0: continue
        P[nm] = limb(nm, Rw('Z', TAILS*math.sin(p - 0.35*i)))
    basis = {}
    for nm in P:
        par = arm.data.bones[nm].parent
        parname = par.name if par else None
        parentP = P.get(parname, M0.get(parname, Matrix())) if parname else Matrix()
        basis[nm] = (parentP @ REL[nm]).inverted() @ P[nm]
    return basis

arm.animation_data.action = None
for f in range(1, NF+1):
    basis = build_pose((f-1)/(NF-1))
    for nm, B in basis.items():
        pb = arm.pose.bones[nm]; pb.matrix_basis = B
        pb.keyframe_insert('rotation_quaternion', frame=f)
        pb.keyframe_insert('location', frame=f)
act = arm.animation_data.action; act.name = 'Walk'
for fc in all_fcurves(act):
    for kp in fc.keyframe_points: kp.interpolation='LINEAR'
bpy.context.view_layer.update()
print('[W4] keyed', NF, 'fcurves', len(all_fcurves(act)))

meshes = [bpy.data.objects[n] for n in ('DragonMan_Body','DragonMan_Foot.L','DragonMan_Foot.R')]
def minz():
    m=1e9
    for ob in meshes:
        obe=ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); me=obe.to_mesh(); M=ob.matrix_world
        for v in me.vertices:
            z=(M@v.co).z
            if z<m: m=z
        obe.to_mesh_clear()
    return m
root_curves = {fc.array_index: fc for fc in all_fcurves(act) if fc.data_path=='pose.bones["mixamorig:Root"].location'}
locmap = (M3 @ REL['mixamorig:Root'].to_3x3()).inverted()
for it in range(6):
    worst=0.0
    for f in range(1, NF+1):
        sc.frame_set(f); bpy.context.view_layer.update()
        m = minz(); worst = max(worst, abs(m-0.0005))
        dz = 0.0005 - m
        if abs(dz) < 5e-4: continue
        v = locmap @ Vector((0,0,dz))
        for ax in range(3):
            fc = root_curves.get(ax)
            if not fc: continue
            for kp in fc.keyframe_points:
                if abs(kp.co[0]-f) < 0.01:
                    kp.co[1] += v[ax]; kp.handle_left[1] += v[ax]; kp.handle_right[1] += v[ax]; break
    print('[W4] ground iter', it, 'worst', round(worst,5))
    if worst < 0.0015: break
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[W4] saved', OUTB)
