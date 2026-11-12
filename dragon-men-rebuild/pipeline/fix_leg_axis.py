# fix_leg_axis.py -- re-plane the leg swing: conjugate leg bone world rotations by a rotation about Z
import bpy, sys, json, math
from mathutils import Matrix
a = sys.argv[sys.argv.index('--')+1:]
O = {}
i=0
while i<len(a):
    if a[i].startswith('--'):
        k=a[i].lstrip('-'); v=a[i+1] if i+1<len(a) and not a[i+1].startswith('--') else '1'
        O[k]=v; i+=2 if (i+1<len(a) and not a[i+1].startswith('--')) else 1
    else: i+=1
SRC, OUTB = O['src'], O['out-blend']
DEG = float(O.get('deg','90'))
SIDE = O.get('side','both')
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
R = Matrix.Rotation(math.radians(DEG), 3, 'Z'); Rt = R.transposed()
sides = ['Left','Right'] if SIDE=='both' else [SIDE]
chain = []
for s in sides:
    chain += ['mixamorig:%sUpLeg'%s, 'mixamorig:%sLeg'%s, 'mixamorig:%sFoot'%s,
              'mixamorig:%sToeBase'%s, 'mixamorig:%sToeEnd'%s, 'mixamorig:%sToe02End'%s,
              'mixamorig:%sToe02End.001'%s, 'mixamorig:%sToe03Base'%s, 'mixamorig:%sToe03End'%s]
done = {}
for act_name in ('Walk','Run'):
    act = bpy.data.actions.get(act_name)
    if not act: continue
    arm.animation_data.action = act
    fr = [int(round(x)) for x in act.frame_range]
    for f in range(fr[0], fr[1]+1):
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
        for bn in chain:
            pb = arm.pose.bones.get(bn)
            if not pb: continue
            M = pb.matrix.copy()
            rot = M.to_3x3().normalized()
            new = R @ rot @ Rt
            T = Matrix.Translation(M.translation) @ new.to_4x4()
            pb.matrix = T
            bpy.context.view_layer.update()
            pb.keyframe_insert('rotation_quaternion', frame=f)
            pb.keyframe_insert('location', frame=f)
    done[act_name] = fr
print('[LA] done', json.dumps(done), 'deg', DEG)
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[LA] saved', OUTB)
