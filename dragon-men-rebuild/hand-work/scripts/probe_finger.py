
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
me=body.data; MW=body.matrix_world; AW=arm.matrix_world
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
root=None
for r,vs in isl.items():
    if sum(1 for v in vs if dom[v]=='mixamorig:LeftHand')>200 and len(vs)>1000: root=r
vset=set(isl[root])
FING=("Index","Middle")
for f in FING:
    pts=[]
    for k in (1,2,3):
        b=arm.data.bones['mixamorig:LeftHand%s%d'%(f,k)]
        if k==1: pts.append(AW@b.head_local)
        pts.append(AW@b.tail_local)
    u=(pts[3]-pts[0]).normalized(); L=(pts[3]-pts[0]).length
    tmp=Vector((0,0,1)) if abs(u.z)<0.9 else Vector((1,0,0))
    vv=u.cross(tmp).normalized(); ww=u.cross(vv).normalized()
    sel=[]
    for i in vset:
        p=MW@me.vertices[i].co; d=p-pts[0]; t=d.dot(u); rad=(d-t*u).length
        if -0.02<=t<=L+0.05 and rad<0.075: sel.append((i,t,rad))
    print("%s verts in cylinder: %d of L=%.4f" % (f,len(sel),L))
    jt=[0, (pts[1]-pts[0]).dot(u), (pts[2]-pts[0]).dot(u), L]
    print("   joint t:", [round(x,4) for x in jt])
    for frac,lab in ((0.25,'p1-mid'),(0.5,'j1'),(0.75,'p2-mid')):
        band=[(t,rad) for i,t,rad in sel if abs(t-jt[0]-(jt[3]-jt[0])*frac)<0.006]
        if band:
            rr=[b[1] for b in band]
            print("     %s t~%.3f n=%d r=%.4f..%.4f mean=%.4f" % (lab, sum(b[0] for b in band)/len(band), len(band), min(rr), max(rr), sum(rr)/len(rr)))
    # fewest-radius neighbours: radial extent by angle in slab near j1
    band=[(i,t,rad) for i,t,rad in sel if abs(t-jt[1])<0.012]
    band.sort(key=lambda x:x[2])
    print("     near j1 slab n=%d  rlist=%s" % (len(band), [round(b[2],4) for b in band][:40]))
# isolate Index finger mesh for render
f="Index"
pts=[]
for k in (1,2,3):
    b=arm.data.bones['mixamorig:LeftHand%s%d'%(f,k)]
    if k==1: pts.append(AW@b.head_local)
    pts.append(AW@b.tail_local)
u=(pts[3]-pts[0]).normalized(); L=(pts[3]-pts[0]).length
selv=set()
for i in vset:
    p=MW@me.vertices[i].co; d=p-pts[0]; t=d.dot(u); rad=(d-t*u).length
    if -0.03<=t<=L+0.06: selv.add(i)
polys=[p for p in me.polygons if all(v in selv for v in p.vertices)]
print("index subset verts",len(selv),"polys",len(polys))
verts=[]; idx={}
for p in polys:
    for v in p.vertices:
        if v not in idx: idx[v]=len(verts); verts.append(MW@me.vertices[v].co)
nm=bpy.data.meshes.new('iso'); nm.from_pydata([tuple(v) for v in verts],[],[[idx[v] for v in p.vertices] for p in polys]); nm.update()
iso=bpy.data.objects.new('iso',nm); sc.collection.objects.link(iso); body.hide_render=True
clay=bpy.data.materials.new('clay'); clay.use_nodes=True
bs=clay.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value=(0.6,0.6,0.62,1); bs.inputs['Roughness'].default_value=0.5
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
c=(pts[0]+pts[3])/2; target=(c.x,c.y,c.z)
shot('fin_Lindex_axis.png',target,tuple(-u),0.30)
shot('fin_Lindex_side.png',target,(1,0,0),0.30)
shot('fin_Lindex_top.png',target,(0,0,1),0.30)
print("DONE")
