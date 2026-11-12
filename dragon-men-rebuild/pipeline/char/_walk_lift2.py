import bpy
from mathutils import Vector
P=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody/char_rig.blend'
bpy.ops.wm.open_mainfile(filepath=P)
sc=bpy.context.scene; rig=bpy.data.objects['Human.rig']; human=bpy.data.objects['Human']
root=rig.pose.bones['root']; R3=root.bone.matrix_local.to_3x3(); Ri=R3.inverted()
def minz():
    dg=bpy.context.evaluated_depsgraph_get(); ev=human.evaluated_get(dg); me=ev.to_mesh()
    m=min((human.matrix_world@v.co).z for v in me.vertices); ev.to_mesh_clear(); return m
for f in range(1,34):
    sc.frame_set(f); root.location=(0,0,0); root.keyframe_insert('location', frame=f)
base=[]
for f in range(1,34):
    sc.frame_set(f); bpy.context.view_layer.update(); base.append(minz())
print('BASE',[round(x,4) for x in base])
for f in range(1,34):
    sc.frame_set(f); bpy.context.view_layer.update()
    root.location = Ri @ Vector((0,0,-base[f-1])); root.keyframe_insert('location', frame=f)
after=[]
for f in range(1,34):
    sc.frame_set(f); bpy.context.view_layer.update(); after.append(minz())
print('AFTER',[round(x,4) for x in after])
bpy.ops.wm.save_as_mainfile(filepath=P)
print('DONE')