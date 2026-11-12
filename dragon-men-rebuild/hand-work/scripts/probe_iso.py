
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
mats=[m.name if m else '?' for m in me.materials]
# left palm island
target_root=None
for r,vs in isl.items():
    if sum(1 for v in vs if dom[v]=='mixamorig:LeftHand')>200 and len(vs)>1000: target_root=r
vs=set(isl[target_root]); print("palm island verts",len(vs))
polys=[p for p in me.polygons if all(v in vs for v in p.vertices)]
print("palm island polys",len(polys), "mat hist", {mats[m]:sum(1 for p in polys if p.material_index==m) for m in set(p.material_index for p in polys)})
# build isolated mesh in world coords
verts=[]; idx={}
for p in polys:
    for v in p.vertices:
        if v not in idx: idx[v]=len(verts); verts.append(MW@me.vertices[v].co)
faces=[[idx[v] for v in p.vertices] for p in polys]
nm=bpy.data.meshes.new('palmiso')
nm.from_pydata([tuple(v*1.0) for v in verts],[],faces); nm.update()
# put in world space: object at identity
iso=bpy.data.objects.new('palmiso',nm); sc.collection.objects.link(iso)
# hide body
body.hide_render=True
clay=bpy.data.materials.new('clay'); clay.use_nodes=True
bs=clay.node_tree.nodes.get('Principled BSDF')
bs.inputs['Base Color'].default_value=(0.6,0.6,0.62,1); bs.inputs['Roughness'].default_value=0.5
nm.materials.append(clay)
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=16; sc.cycles.use_denoising=True
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
target=(c.x,c.y,c.z)
shot('iso_L_palmX.png',target,(1,0,0),0.40)
shot('iso_L_backX.png',target,(-1,0,0),0.40)
shot('iso_L_topZ.png',target,(0,0,1),0.40)
shot('iso_L_edgeB.png',target,(1,1,0),0.40)
print("DONE")
