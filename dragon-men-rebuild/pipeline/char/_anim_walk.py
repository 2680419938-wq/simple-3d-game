import bpy, math
from mathutils import Vector
P=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody/char_rig.blend'
OUT=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody'
bpy.ops.wm.open_mainfile(filepath=P)
sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE'; sc.view_settings.view_transform='Standard'
sc.render.resolution_x=460; sc.render.resolution_y=760
w=bpy.data.worlds.new('W'); w.use_nodes=True; [n for n in w.node_tree.nodes if n.type=='BACKGROUND'][0].inputs[0].default_value=(0.035,0.035,0.05,1); sc.world=w
for i,(loc,en) in enumerate([((-2,-3,3.0),420),((2.5,-2.5,2.2),260),((0,3,2.6),220)]):
    l=bpy.data.lights.new('L%d'%i,'AREA'); l.energy=en; l.size=4
    ob=bpy.data.objects.new('L%d'%i,l); sc.collection.objects.link(ob); ob.location=loc
    ob.rotation_euler=(Vector((0,0,1.2))-Vector(loc)).to_track_quat('-Z','Y').to_euler()
cam=bpy.data.cameras.new('C'); co=bpy.data.objects.new('C',cam); sc.collection.objects.link(co); sc.camera=co
cam.type='ORTHO'; cam.clip_start=0.1; cam.clip_end=100; cam.ortho_scale=2.4
C=Vector((0,0,1.02))
rig=bpy.data.objects['Human.rig']
for b in rig.pose.bones: b.rotation_mode='XYZ'
def R(n,ax,deg):
    b=rig.pose.bones.get(n)
    if b is None: print('MISS',n); return
    b.rotation_euler[ax]=math.radians(deg)
NF=32
for f in range(NF+1):
    t=f/NF; ph=2*math.pi*t
    R('upperleg01.L',0, 24*math.sin(ph)); R('upperleg01.R',0, 24*math.sin(ph+math.pi))
    R('lowerleg01.L',0, -max(0.0, 46*math.sin(ph-1.9))-4); R('lowerleg01.R',0, -max(0.0, 46*math.sin(ph+math.pi-1.9))-4)
    R('foot.L',0, 14*math.sin(ph-0.6)); R('foot.R',0, 14*math.sin(ph+math.pi-0.6))
    R('upperarm01.L',0, -18*math.sin(ph)); R('upperarm01.R',0, -18*math.sin(ph+math.pi))
    R('lowerarm01.L',1, -12-8*math.sin(ph)); R('lowerarm01.R',1, 12+8*math.sin(ph))
    R('spine01',1, 3*math.sin(ph)); R('spine02',1, -3*math.sin(ph))
    R('clavicle.L',0, 3*math.sin(ph)); R('clavicle.R',0, 3*math.sin(ph))
    R('tail01',2, 9*math.sin(ph)); R('tail02',2, 9*math.sin(ph-0.8)); R('tail03',2, 9*math.sin(ph-1.6))
    pel=rig.pose.bones.get('pelvis.L')
    if pel: pel.location=(0,0,0.018*math.cos(2*ph))
    R('neck01',0, -3*math.sin(2*ph))
    for b in rig.pose.bones:
        b.keyframe_insert('rotation_euler', frame=f+1)
        if b.name=='pelvis.L': b.keyframe_insert('location', frame=f+1)
act=rig.animation_data.action; act.name='Walk'; act.use_cyclic=True
print('ACT',act.name,len(act.fcurves) if hasattr(act,'fcurves') else 'na', act.frame_range[:])
for f in (1,9,17,25):
    sc.frame_set(f)
    for tag,a in (('side',90),('q34',35)):
        ang=math.radians(a); dv=Vector((math.sin(ang),-math.cos(ang),0)); p=C+dv*6
        co.location=p; co.rotation_euler=(C-p).to_track_quat('-Z','Y').to_euler()
        sc.render.filepath=OUT+'/walk_f%02d_%s.png'%(f,tag); bpy.ops.render.render(write_still=True)
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=P)
print('DONE')