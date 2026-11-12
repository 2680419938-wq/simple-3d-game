
# -*- coding: utf-8 -*-
import bpy, os, json, math
from collections import defaultdict
from mathutils import Vector, Quaternion
OUT = r"D:\ai\建模\dragon-men-rebuild\hand-work"
arm = bpy.data.objects['DragonMan_Rig']; body = bpy.data.objects['DragonMan_Body']
if arm.animation_data: arm.animation_data_clear()
print("ACTIONS on arm after clear:", arm.animation_data)
me = body.data; MW=body.matrix_world; AW=arm.matrix_world
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
FING=("Thumb","Index","Middle","Ring")
for side in ("Left",):
    for f in FING:
        pts=[]
        for k in (1,2,3):
            b=arm.data.bones['mixamorig:%sHand%s%d'%(side,f,k)]
            if k==1: pts.append(AW@b.head_local)
            pts.append(AW@b.tail_local)
        u=(pts[3]-pts[0]).normalized()
        tmp=Vector((0,0,1)) if abs(u.z)<0.9 else Vector((1,0,0))
        vv=u.cross(tmp).normalized()
        boneNs=set('mixamorig:%sHand%s%d'%(side,f,k) for k in (1,2,3))
        rows=[]
        for i in range(n):
            if dom[i] not in boneNs: continue
            p=MW@me.vertices[i].co; d=p-pts[0]; t=d.dot(u); rad=(d-t*u).length
            if rad>0.045: continue
            rows.append((t,rad,i))
        rows.sort()
        # cluster by gap
        rings=[]; cur=[]
        for t,rad,i in rows:
            if cur and t-cur[-1][0]>0.006:
                rings.append(cur); cur=[]
            cur.append((t,rad,i))
        if cur: rings.append(cur)
        seg=[ (round(sum(x[0] for x in r)/len(r),4), round(sum(x[1] for x in r)/len(r),4), len(r)) for r in rings]
        print("%s %s L=%.4f jointt=%s nrings=%d" % (side,f,(pts[3]-pts[0]).length,
            [round((pts[k]-pts[0]).dot(u),4) for k in range(4)], len(rings)))
        print("   rings t/rad/n:", seg)
print("PROFILE DONE")
