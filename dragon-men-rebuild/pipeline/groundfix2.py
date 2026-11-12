# groundfix2.py -- two-pass ground contact: measure all frames, then apply, then verify
import bpy, sys, json
from mathutils import Matrix
a = sys.argv[sys.argv.index('--')+1:]
O = {}
i=0
while i<len(a):
    if a[i].startswith('--'):
        k=a[i].lstrip('-'); v=a[i+1] if i+1<len(a) and not a[i+1].startswith('--') else '1'
        O[k]=v; i+=2 if (i+1<len(a) and not a[i+1].startswith('--')) else 1
    else: i+=1
SRC, OUTB, ACT = O['src'], O['out-blend'], O.get('action','Walk')
TARGET = float(O.get('target','0.0005'))
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']; arm.data.pose_position='POSE'
sc = bpy.context.scene
act = bpy.data.actions[ACT]
if arm.animation_data is None: arm.animation_data_create()
arm.animation_data.action = act
try:
    sl = list(act.slots)
    if sl: arm.animation_data.action_slot = sl[0]
except Exception: pass
meshes = [bpy.data.objects[n] for n in ('DragonMan_Body','DragonMan_Foot.L','DragonMan_Foot.R')]
def minz():
    m = 1e9
    for ob in meshes:
        obe = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = obe.to_mesh()
        M = ob.matrix_world
        for v in me.vertices:
            z = (M @ v.co).z
            if z < m: m = z
        obe.to_mesh_clear()
    return m
f0, f1 = [int(round(x)) for x in act.frame_range]
measured = {}
for f in range(f0, f1+1):
    sc.frame_set(f); bpy.context.view_layer.update(); measured[f] = minz()
hinge = arm.pose.bones['mixamorig:Hips']
base_loc = {}
for f in range(f0, f1+1):
    sc.frame_set(f); bpy.context.view_layer.update()
    base_loc[f] = hinge.matrix.copy()
for f in range(f0, f1+1):
    sc.frame_set(f)
    M = base_loc[f].copy()
    M.translation = M.translation + Matrix.Translation((0,0,TARGET-measured[f])).to_translation()
    hinge.matrix = M
    bpy.context.view_layer.update()
    hinge.keyframe_insert('location', frame=f)
    hinge.keyframe_insert('rotation_quaternion', frame=f)
verify = {}
for f in range(f0, f1+1):
    sc.frame_set(f); bpy.context.view_layer.update(); verify[f] = round(minz(),5)
print('[G2] verify', [verify[f] for f in range(f0,f1+1)])
print('[G2] worst', min(verify.values()), max(verify.values()))
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[G2] saved', OUTB)
