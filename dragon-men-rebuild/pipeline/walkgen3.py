# walkgen3.py -- procedural walk in WORLD space (legs swing about world X, arms lower about world Y)
import bpy, sys, math
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
NF = int(O.get('frames','33'))
SWING = float(O.get('swing','24')); KNEE = float(O.get('knee','38')); ARMDN = float(O.get('armdn','62'))
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']; arm.data.pose_position='POSE'
sc = bpy.context.scene; sc.render.fps = 30
M3 = arm.matrix_world.to_3x3(); M3i = M3.inverted()
arm.animation_data_create()
for nm in ('Walk','Run'):
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
    par = b.parent
    REL[b.name] = (par.matrix_local.inverted() @ b.matrix_local) if par else b.matrix_local.copy()
M0 = {}
for b in arm.data.bones:
    M0[b.name] = (M0[b.parent.name] @ REL[b.name]) if b.parent else REL[b.name].copy()

def Rw(axis, deg): return Matrix.Rotation(math.radians(deg), 3, axis)
def limb(nm, Rext, head=None):
    if head is None:
        par = arm.data.bones[nm].parent
        parname = par.name if par else None
        base = P.get(parname, M0.get(parname, Matrix())) if parname else Matrix()
        head = (base @ REL[nm]).translation
    R = M3i @ Rext @ M3 @ M0[nm].to_3x3()
    return Matrix.Translation(head) @ R.to_4x4()

LEGS = [('UpLeg',0.0),('Leg',0.0),('Foot',0.0),('ToeBase',0.0),('ToeEnd',0.0),
        ('Toe02End',0.0),('Toe02End.001',0.0),('Toe03Base',0.0),('Toe03End',0.0)]

def build_pose(t):
    global P
    p = 2*math.pi*t
    P = {}
    P['mixamorig:Root'] = M0['mixamorig:Root'].copy()
    hips_head = M0['mixamorig:Hips'].translation + Vector((0,0,0.012*math.cos(2*p)))
    P['mixamorig:Hips'] = Matrix.Translation(hips_head) @ (M3i @ Rw('X',4.0) @ M3 @ M0['mixamorig:Hips'].to_3x3()).to_4x4()
    for s, ph, sgn in (('Left',0.0,1.0), ('Right',math.pi,-1.0)):
        th = SWING*math.sin(p+ph)
        knee = 6.0 + max(0.0, KNEE*math.sin(p+ph+2.4))
        fa = max(-20.0, min(20.0, 0.45*(th-knee)))
        for bn, deg in (('UpLeg',th),('Leg',th-knee),('Foot',fa),('ToeBase',fa),('ToeEnd',fa),
                        ('Toe02End',fa),('Toe02End.001',fa),('Toe03Base',fa),('Toe03End',fa)):
            nm = 'mixamorig:%s%s' % (s, bn)
            if nm not in M0: continue
            P[nm] = limb(nm, Rw('X', deg))
        sw = 12.0*math.sin(p+ph)
        for bn, extra in (('Arm',0.0),('ForeArm',18.0),('Hand',18.0)):
            nm = 'mixamorig:%s%s' % (s, bn)
            if nm not in M0: continue
            Rext = Rw('X', sw+extra) @ Rw('Y', ARMDN*sgn)
            P[nm] = limb(nm, Rext)
    basis = {}
    for nm in P:
        par = arm.data.bones[nm].parent
        parname = par.name if par else None
        parentP = P.get(parname, M0.get(parname, Matrix())) if parname else Matrix()
        basis[nm] = (parentP @ REL[nm]).inverted() @ P[nm]
    return basis

arm.animation_data.action = None
act = None
for f in range(1, NF+1):
    basis = build_pose((f-1)/(NF-1))
    for nm, B in basis.items():
        pb = arm.pose.bones[nm]
        pb.matrix_basis = B
        pb.keyframe_insert('rotation_quaternion', frame=f)
        pb.keyframe_insert('location', frame=f)
    if act is None: act = arm.animation_data.action
act = arm.animation_data.action; act.name = 'Walk'
for fc in all_fcurves(act):
    for kp in fc.keyframe_points: kp.interpolation='LINEAR'
bpy.context.view_layer.update()
print('[W3] keyed', NF, 'fcurves', len(all_fcurves(act)))

meshes = [bpy.data.objects[n] for n in ('DragonMan_Body','DragonMan_Foot.L','DragonMan_Foot.R')]
def minz():
    m=1e9; zmin=None
    for ob in meshes:
        obe=ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); me=obe.to_mesh(); M=ob.matrix_world
        for v in me.vertices:
            z=(M@v.co).z
            if z<m: m=z
        obe.to_mesh_clear()
    return m
root_curves = {fc.array_index: fc for fc in all_fcurves(act) if fc.data_path=='pose.bones["mixamorig:Root"].location'}
locmap = REL['mixamorig:Root'].to_3x3().inverted()
for it in range(5):
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
    print('[W3] ground iter', it, 'worst', round(worst,5))
    if worst < 0.002: break
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[W3] saved', OUTB)
