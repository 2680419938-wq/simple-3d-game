
# -*- coding: utf-8 -*-
import bpy, sys, os, math
from mathutils import Vector, Quaternion
argv=sys.argv[sys.argv.index('--')+1:]
BLEND, OUT = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc=bpy.context.scene
arm=bpy.data.objects['DragonMan_Rig']
if arm.animation_data: arm.animation_data_clear()
# clay material override on all meshes
clay=bpy.data.materials.new('clay'); clay.use_nodes=True
bs=clay.node_tree.nodes.get('Principled BSDF')
bs.inputs['Base Color'].default_value=(0.55,0.55,0.58,1); bs.inputs['Roughness'].default_value=0.45
for o in bpy.data.objects:
    if o.type=='MESH':
        o.data.materials.clear(); o.data.materials.append(clay)
        for p in o.data.polygons: p.material_index=0
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=14; sc.cycles.use_denoising=True
sc.render.resolution_x=sc.render.resolution_y=640
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
bgn=w.node_tree.nodes.new('ShaderNodeBackground'); bgn.inputs[0].default_value=(0.5,0.52,0.58,1); bgn.inputs[1].default_value=1.4
ow=w.node_tree.nodes.new('ShaderNodeOutputWorld'); w.node_tree.links.new(bgn.outputs[0],ow.inputs[0])
sd=bpy.data.lights.new('S','SUN'); sd.energy=4.5
sun=bpy.data.objects.new('S',sd); sc.collection.objects.link(sun); sun.rotation_euler=(math.radians(50),0,math.radians(35))
fd=bpy.data.lights.new('F','SUN'); fd.energy=2.2
fill=bpy.data.objects.new('F',fd); sc.collection.objects.link(fill); fill.rotation_euler=(math.radians(75),0,math.radians(-120))
cd=bpy.data.cameras.new('C'); cd.type='ORTHO'; cam=bpy.data.objects.new('C',cd); sc.collection.objects.link(cam); sc.camera=cam
def shot(name,target,d,ortho):
    cam.data.ortho_scale=ortho
    cam.location=Vector(target)+Vector(d).normalized()*8
    cam.rotation_euler=(Vector(target)-cam.location).normalized().to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=os.path.join(OUT,name); bpy.ops.render.render(write_still=True); print('[R]',name,flush=True)
side=argv[2]; tag=side[0]
b1=arm.data.bones['mixamorig:%sHandMiddle1'%side]; b3=arm.data.bones['mixamorig:%sHandRing3'%side]
c=arm.matrix_world@((b1.head_local+b3.tail_local)/2); target=(c.x,c.y,c.z)
for nm,d in (('palmX',(1,0,0)),('backX',(-1,0,0)),('topZ',(0,0,1)),('sideY',(-1,0,0.001))):
    shot('clay_%s_%s.png'%(tag,nm), target, d, 0.42)
print("DONE")
