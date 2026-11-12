
# -*- coding: utf-8 -*-
import bpy, sys, os, math
from collections import defaultdict
from mathutils import Vector
argv=sys.argv[sys.argv.index('--')+1:]
BLEND, OUT = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc=bpy.context.scene
arm=bpy.data.objects['DragonMan_Rig']; body=bpy.data.objects['DragonMan_Body']
if arm.animation_data: arm.animation_data_clear()
me=body.data; MW=body.matrix_world
n=len(me.vertices); par=list(range(n))
def find(a):
    while par[a]!=a: par[a]=par[par[a]]; a=par[a]
    return a
def union(a,b):
    ra,rb=find(a),find(b)
    if ra!=rb: par[ra]=rb
for e in me.edges: union(e.vertices[0],e.vertices[1])
isl=defaultdict(list)
for i in range(n): isl[find(i)].append(i)
gname={g.index:g.name for g in body.vertex_groups}
dom=[None]*n
for v in me.vertices:
    bw=-1
    for ge in v.groups:
        if ge.weight>bw: bw=ge.weight; dom[v.index]=gname[ge.group]
for side in ("Left","Right"):
    for r,vs in isl.items():
        if sum(1 for v in vs if dom[v]=='mixamorig:%sHand'%side)>200:
            co=[MW@me.vertices[v].co for v in vs]
            mn=[min(c[i] for c in co) for i in range(3)]; mx=[max(c[i] for c in co) for i in range(3)]
            print("%s hand island n=%d worldbbox=%s..%s"%(side,len(vs),[round(x,3) for x in mn],[round(x,3) for x in mx]))
clay=bpy.data.materials.new('clay'); clay.use_nodes=True
bs=clay.node_tree.nodes.get('Principled BSDF')
bs.inputs['Base Color'].default_value=(0.55,0.55,0.58,1); bs.inputs['Roughness'].default_value=0.45
for o in bpy.data.objects:
    if o.type=='MESH':
        o.data.materials.clear(); o.data.materials.append(clay)
        for p in o.data.polygons: p.material_index=0
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=14; sc.cycles.use_denoising=True
sc.render.resolution_x=sc.render.resolution_y=560
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
c=arm.matrix_world@((arm.data.bones['mixamorig:LeftHandMiddle1'].head_local+arm.data.bones['mixamorig:LeftHandRing3'].tail_local)/2)
target=(c.x,c.y,c.z); print("target",[round(v,3) for v in target])
shot('wide_L_palmX.png', target, (1,0,0), 0.95)
shot('wide_L_topZ.png', target, (0,0,1), 0.95)
shot('wide_L_armY.png', target, (0,1,0), 0.95)
print("DONE")
