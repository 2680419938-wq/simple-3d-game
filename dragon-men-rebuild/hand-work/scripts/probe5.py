
# -*- coding: utf-8 -*-
import bpy, json, os
from collections import defaultdict
from mathutils import Vector
arm=bpy.data.objects['DragonMan_Rig']; body=bpy.data.objects['DragonMan_Body']
me=body.data; MW=body.matrix_world; AW=arm.matrix_world
mats=[m.name if m else '?' for m in me.materials]
print("mats:", mats)
# vertex->materials
vmat=defaultdict(set)
for p in me.polygons:
    for v in p.vertices: vmat[v].add(mats[p.material_index])
side='Left'
for f in ("Thumb","Index","Middle","Ring"):
    pts=[]
    for k in (1,2,3):
        b=arm.data.bones['mixamorig:%sHand%s%d'%(side,f,k)]
        if k==1: pts.append(AW@b.head_local)
        pts.append(AW@b.tail_local)
    u=(pts[3]-pts[0]).normalized(); tmp=Vector((0,0,1)) if abs(u.z)<0.9 else Vector((1,0,0))
    L=(pts[3]-pts[0]).length
    print("=== %s %s L=%.4f joints=%s" % (side,f,L,[round((pts[k]-pts[0]).dot(u),3) for k in range(4)]))
    # gather verts within 0.05 of axis, t in [-0.02, L+0.06]
    rows=[]
    for i in range(len(me.vertices)):
        p=MW@me.vertices[i].co; d=p-pts[0]; t=d.dot(u); rad=(d-t*u).length
        if -0.02<=t<=L+0.07 and rad<=0.055: rows.append((t,rad,i))
    # histogram t bins of 0.01
    hb=defaultdict(lambda: defaultdict(int))
    for t,rad,i in rows:
        tb=round(t/0.01)*0.01
        rb=round(rad/0.005)*0.005
        for m in (vmat.get(i) or {'?'}): hb[tb][(m,rb)]+=1
    for tb in sorted(hb):
        s=defaultdict(int)
        for (m,rb),c in hb[tb].items(): s[m]+=c
        rmax=max((rb for (m,rb) in hb[tb]), default=0); rmin=min((rb for (m,rb) in hb[tb]), default=0)
        print("  t=%.3f n=%3d r=%.3f..%.3f %s" % (tb, sum(s.values()), rmin, rmax, dict(s)))
print("DONE")
