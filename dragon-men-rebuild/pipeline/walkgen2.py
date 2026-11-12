# walkgen2.py -- procedural walk with math-based pose (no depsgraph resets) + ground pass via fcurve edits
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
NF = int(O.get('frames','33'))
SWING = float(O.get('swing','24')); KNEE = float(O.get('knee','38')); ARMDN = float(O.get('armdn','62'))
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']; arm.data.pose_position='POSE'
sc = bpy.context.scene; sc.render.fps = 30
arm.animation_data_create()
old = bpy.data.actions.get('Walk')
if old: bpy.data.actions.remove(old)

def all_fcurves(x):
    if hasattr(x,'fcurves'): return list(x.fcurves)
    out=[]
    for layer in x.layers:
        for strip in layer.strips:
            for cb in strip.channelbags: out.extend(cb.fcurves)
    return out

# rest data
REL = {}
for b in arm.data.bones:
    par = b.parent
    REL[b.name] = (par.matrix_local.inverted() @ b.matrix_local) if par else b.matrix_local.copy()
R0 = {}
for b in arm.pose.bones:
    R0[b.name] = b.matrix_basis.copy()  # identity
# rest world (armature-space) matrices with identity pose
M0 = {}
for b in arm.data.bones:
    if b.parent:
        M0[b.name] = M0[b.parent.name] @ REL[b.name]
    else:
        M0[b.name] = REL[b.name].copy()
X = Vector((1,0,0)); Z = Vector((0,0,1))
def rx(d): return Matrix.Rotation(math.radians(d),3,'X')

ORDER = ['mixamorig:Root','mixamorig:Hips']
for s in ('Left','Right'):
    ORDER += ['mixamorig:%sUpLeg'%s,'mixamorig:%sLeg'%s,'mixamorig:%sFoot'%s,
              'mixamorig:%sToeBase'%s,'mixamorig:%sToeEnd'%s,'mixamorig:%sToe02End'%s,
              'mixamorig:%sToe02End.001'%s,'mixamorig:%sToe03Base'%s,'mixamorig:%sToe03End'%s]
for s in ('Left','Right'):
    ORDER += ['mixamorig:%sArm'%s,'mixamorig:%sForeArm'%s,'mixamorig:%sHand'%s]
ORDER = [n for n in ORDER if n in M0]

def build_pose(t, dz):
    p = 2*math.pi*t
    P = {}
    hips_head = M0['mixamorig:Hips'].translation + Vector((0,0,0.012*math.cos(2*p)+dz))
    P['mixamorig:Root'] = M0['mixamorig:Root'].copy()
    P['mixamorig:Hips'] = Matrix.Translation(M0['mixamorig:Hips'].translation + Vector((0,0,0.012*math.cos(2*p)+dz))) @ (rx(4.0) @ M0['mixamorig:Hips'].to_3x3()).to_4x4()
    for s, ph in (('Left',0.0), ('Right',math.pi)):
        th = SWING*math.sin(p+ph)
        knee = max(0.0, KNEE*math.sin(p+ph+2.2)) + 6.0
        fa = max(-20.0, min(20.0, 0.45*(th - knee)))
        for bn, deg in (('%sUpLeg', th), ('%sLeg', th - knee), ('%sFoot', fa),
                        ('%sToeBase', fa), ('%sToeEnd', fa), ('%sToe02End', fa),
                        ('%sToe02End.001', fa), ('%sToe03Base', fa), ('%sToe03End', fa)):
            nm = 'mixamorig:' + (bn % s)
            if nm not in M0: continue
            par = arm.data.bones[nm].parent.name
            base = P.get(par) if par in P else (M0[par] if par in M0 else Matrix())
            head = (base @ REL[nm]).translation
            P[nm] = Matrix.Translation(head) @ (rx(deg) @ M0[nm].to_3x3()).to_4x4()
    for s, sgn, ph in (('Left', 1.0, math.pi), ('Right', -1.0, 0.0)):
        up = 'mixamorig:%sArm'%s
        rest_dir = (M0[up].to_3x3() @ Vector((0,1,0))).normalized()
        sw = 12.0*math.sin(p+ph)
        tgt = (Quaternion(Z, math.radians(-ARMDN*sgn)) @ Quaternion(X, math.radians(sw)) @ rest_dir).normalized()
        q = rest_dir.rotation_difference(tgt)
        head = M0[up].translation
        P[up] = Matrix.Translation(head) @ (q.to_matrix() @ M0[up].to_3x3()).to_4x4()
        for bn, extra in (('%sForeArm', 18.0), ('%sHand', 18.0)):
            fo = 'mixamorig:' + (bn % s)
            rfd = (M0[fo].to_3x3() @ Vector((0,1,0))).normalized()
            tf = (Quaternion(Z, math.radians(-ARMDN*sgn)) @ Quaternion(X, math.radians(sw+extra)) @ rfd).normalized()
            qf = rfd.rotation_difference(tf)
            par = arm.data.bones[fo].parent.name
            head = (P.get(par, M0.get(par)) @ REL[fo]).translation
            P[fo] = Matrix.Translation(head) @ (qf.to_matrix() @ M0[fo].to_3x3()).to_4x4()
    # convert to bases
    basis = {}
    for nm in ORDER:
        par = arm.data.bones[nm].parent
        parname = par.name if par else None
        parentP = P.get(parname, M0.get(parname, Matrix())) if parname else Matrix()
        basis[nm] = (parentP @ REL[nm]).inverted() @ P[nm]
    return basis

arm.animation_data.action = None
act = None
for f in range(1, NF+1):
    t = (f-1)/(NF-1)
    basis = build_pose(t, 0.0)
    for nm, B in basis.items():
        pb = arm.pose.bones[nm]
        pb.matrix_basis = B
        pb.keyframe_insert('rotation_quaternion', frame=f)
        pb.keyframe_insert('location', frame=f)
    if act is None: act = arm.animation_data.action
act = arm.animation_data.action; act.name = 'Walk'
for fc in all_fcurves(act):
    for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
bpy.context.view_layer.update()
print('[W2] keyed', NF, 'frames, fcurves', len(all_fcurves(act)))

# ground pass: adjust Hips location keys per frame
meshes = [bpy.data.objects[n] for n in ('DragonMan_Body','DragonMan_Foot.L','DragonMan_Foot.R')]
def minz():
    m = 1e9
    for ob in meshes:
        obe = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = obe.to_mesh(); M = ob.matrix_world
        for v in me.vertices:
            z = (M@v.co).z
            if z < m: m = z
        obe.to_mesh_clear()
    return m
root_curves = {fc.array_index: fc for fc in all_fcurves(act) if fc.data_path == 'pose.bones["mixamorig:Root"].location'}
locmap = REL['mixamorig:Root'].to_3x3().inverted()
print('[W2] root curves', sorted(root_curves.keys()))
for it in range(4):
    worst = 0.0
    for f in range(1, NF+1):
        sc.frame_set(f); bpy.context.view_layer.update()
        m = minz()
        worst = max(worst, abs(m - 0.0005))
        dz = 0.0005 - m
        if abs(dz) < 1e-4: continue
        v = locmap @ Vector((0,0,dz))
        for ax in range(3):
            fc = root_curves.get(ax)
            if not fc: continue
            for kp in fc.keyframe_points:
                if abs(kp.co[0]-f) < 0.01:
                    kp.co[1] += v[ax]; kp.handle_left[1] += v[ax]; kp.handle_right[1] += v[ax]
                    break
    print('[W2] ground iter', it, 'worst dev', round(worst,5))
    if worst < 0.002: break
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[W2] saved', OUTB)
