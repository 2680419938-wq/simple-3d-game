
# -*- coding: utf-8 -*-
import bpy, sys
from mathutils import Vector
from mathutils.kdtree import KDTree
argv=sys.argv[sys.argv.index('--')+1:]
opt={argv[i].lstrip('-'):argv[i+1] for i in range(0,len(argv)-1,2)}
SRC=opt['src']; OUT=opt['out']
bpy.ops.wm.open_mainfile(filepath=SRC)
ob=bpy.data.objects['DragonMan_Body']; me=ob.data; M=ob.matrix_world
gi={vg.name:vg.index for vg in ob.vertex_groups}
sets=[{gi['mixamorig:LeftUpLeg'],gi['mixamorig:LeftLeg']},{gi['mixamorig:RightUpLeg'],gi['mixamorig:RightLeg']}]
tube=[]
for i,v in enumerate(me.vertices):
    gs={g.group for g in v.groups}
    if gs and any(gs<=s for s in sets): tube.append(i)
print('TUBE',len(tube))
# source: foot objects
src=[]
for nm in ('DragonMan_Foot.L','DragonMan_Foot.R'):
    o=bpy.data.objects.get(nm)
    if not o: continue
    uvl=o.data.uv_layers.active
    MF=o.matrix_world
    uvs={}
    if uvl:
        for l in o.data.loops:
            uvs.setdefault(l.vertex_index, uvl.data[l.index].uv.copy())
    for v in o.data.vertices:
        src.append((MF@v.co, uvs.get(v.index, Vector((0.5,0.5)))))
print('SRC',len(src))
kd=KDTree(len(src))
for i,(p,uv) in enumerate(src): kd.insert(p,i)
kd.balance()
uvl=me.uv_layers.get('map1') or me.uv_layers.active
print('uv layer',uvl.name,'loops',len(me.loops))
lut={}
for idx in tube:
    p=M@me.vertices[idx].co
    co,i,d=kd.find(p)
    lut[idx]=src[i][1]
n=0
for l in me.loops:
    uv=lut.get(l.vertex_index)
    if uv is not None:
        uvl.data[l.index].uv=uv; n+=1
print('UVSET',n)
me.update()
bpy.ops.wm.save_as_mainfile(filepath=OUT); print('SAVED',OUT)
