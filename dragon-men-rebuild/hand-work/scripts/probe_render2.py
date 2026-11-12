
# -*- coding: utf-8 -*-
import bpy, sys, os, math
from mathutils import Vector, Quaternion
argv = sys.argv[sys.argv.index('--')+1:]
BLEND, OUT = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data: arm.animation_data_clear()
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=16; sc.cycles.use_denoising=True
sc.render.resolution_x=sc.render.resolution_y=560
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
bgn=w.node_tree.nodes.new('ShaderNodeBackground'); bgn.inputs[0].default_value=(0.45,0.48,0.55,1); bgn.inputs[1].default_value=1.2
ow=w.node_tree.nodes.new('ShaderNodeOutputWorld'); w.node_tree.links.new(bgn.outputs[0],ow.inputs[0])
sd=bpy.data.lights.new('S','SUN'); sd.energy=5.0
sun=bpy.data.objects.new('S',sd); sc.collection.objects.link(sun); sun.rotation_euler=(math.radians(55),0,math.radians(35))
fd=bpy.data.lights.new('F','SUN'); fd.energy=2.0
fill=bpy.data.objects.new('F',fd); sc.collection.objects.link(fill); fill.rotation_euler=(math.radians(70),0,math.radians(-120))
cd=bpy.data.cameras.new('C'); cd.type='ORTHO'; cam=bpy.data.objects.new('C',cd); sc.collection.objects.link(cam); sc.camera=cam
def shot(name,target,d,ortho):
    cam.data.ortho_scale=ortho
    cam.location=Vector(target)+Vector(d).normalized()*8
    cam.rotation_euler=(Vector(target)-cam.location).normalized().to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=os.path.join(OUT,name); bpy.ops.render.render(write_still=True); print('[R]',name,flush=True)
FING=("Thumb","Index","Middle","Ring")
def curl(side, deg):
    for f in FING:
        for k in (1,2,3):
            pb = arm.pose.bones['mixamorig:%sHand%s%d'%(side,f,k)]
            pb.rotation_mode='QUATERNION'
            if deg==0:
                pb.rotation_quaternion=(1,0,0,0); continue
            b1 = arm.data.bones['mixamorig:%sHand%s1'%(side,f)]
            b3 = arm.data.bones['mixamorig:%sHand%s3'%(side,f)]
            fdir=(b3.tail_local-b1.head_local).normalized()
            hb=arm.data.bones['mixamorig:%sHand'%side]; pn=(hb.tail_local-hb.head_local).normalized()
            ax=fdir.cross(pn).normalized()
            lax=(pb.bone.matrix_local.to_3x3().inverted() @ ax).normalized()
            pb.rotation_quaternion=Quaternion(lax, math.radians(deg/3.0))
    bpy.context.view_layer.update()
for side, tag in (("Left","L"),("Right","R")):
    b1 = arm.data.bones['mixamorig:%sHandMiddle1'%side]
    c = arm.matrix_world @ ((b1.head_local + arm.data.bones['mixamorig:%sHandRing3'%side].tail_local)/2)
    target=(c.x,c.y,c.z)
    for deg in (0, 90):
        curl(side, deg)
        shot('bend_%s_%d_palm.png'%(tag,deg), target, (1,0,0), 0.30)
        shot('bend_%s_%d_back.png'%(tag,deg), target, (-1,0,0), 0.30)
    curl(side, 0)
print("DONE")
