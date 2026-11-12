
# -*- coding: utf-8 -*-
import bpy, os, json, math
from collections import defaultdict
from mathutils import Vector, Quaternion
OUT = r"D:\ai\建模\dragon-men-rebuild\hand-work\verify"
os.makedirs(OUT, exist_ok=True)
arm = bpy.data.objects['DragonMan_Rig']; body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = body.matrix_world
AW = arm.matrix_world
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
# map bone -> island id for nail islands
boneisl=defaultdict(set)
for r,vs in isl.items():
    if len(vs)<=8:
        for v in vs:
            if dom[v]: boneisl[dom[v]].add((r,len(vs)))
print("SMALL ISLANDS by dom bone (size<=8):")
for b in sorted(boneisl):
    if "Hand" in b: print("   %-30s %s" % (b, sorted(boneisl[b])))

FING=("Thumb","Index","Middle","Ring")
data={}
for side in ("Left","Right"):
    data[side]={}
    for f in FING:
        pts=[]
        for k in (1,2,3):
            b=arm.data.bones['mixamorig:%sHand%s%d'%(side,f,k)]
            if k==1: pts.append(AW@b.head_local)
            pts.append(AW@b.tail_local)
        chain=[tuple(p) for p in pts]
        L=sum((pts[i+1]-pts[i]).length for i in range(3))
        # existing skin verts dominated by this finger's bones
        boneNs=set('mixamorig:%sHand%s%d'%(side,f,k) for k in (1,2,3))
        vs=[v for vs2 in isl.values() for v in [] ]
        # collect from islands containing the palm: just scan all verts with dom in boneNs
        vids=[i for i in range(n) if dom[i] in boneNs]
        # frame: origin pts[0], axis u, perpendicular v,w
        u=(pts[3]-pts[0]).normalized()
        tmp=Vector((0,0,1))
        if abs(u.dot(tmp))>0.9: tmp=Vector((1,0,0))
        vv=u.cross(tmp).normalized(); ww=u.cross(vv).normalized()
        prof=[]
        for i in vids:
            p=MW@me.vertices[i].co
            d=p-pts[0]
            t=d.dot(u); rad=(d-t*u).length
            prof.append((t,rad))
        prof.sort()
        # binned profile
        bins=defaultdict(list)
        for t,rad in prof: bins[round(t,4)].append(rad)
        # tip islands
        tips=[]
        for k,(bn) in enumerate(['mixamorig:%sHand%s%d'%(side,f,kk) for kk in (1,2,3)]):
            for r,sz in boneisl.get(bn,()):
                co=[MW@me.vertices[v].co for v in isl[r]]
                tips.append({'bone':bn,'size':sz,'n_isl':len(co),
                    'centroid':[round(x,4) for x in sum(co,Vector())/len(co)],
                    't_range':[round(min((c-pts[0]).dot(u) for c in co),4), round(max((c-pts[0]).dot(u) for c in co),4)],
                    'rad_max':round(max(((c-pts[0])-((c-pts[0]).dot(u))*u).length for c in co),4)})
        data[side][f]={'chain':[[round(x,4) for x in p] for p in chain],'len':round(L,4),
            'n_skin_verts':len(vids),
            'radial_profile':{str(k):[round(min(v),4),round(max(v),4)] for k,v in sorted(bins.items()) if k<=L+0.01},
            'tips':tips, 'u':[round(x,4) for x in u]}
        print("%s %-7s L=%.4f nverts=%d tips=%s" % (side,f,L,len(vids),
            [(t['bone'][-6:],t['size'],t['t_range'],t['rad_max']) for t in tips]))
        ts=sorted(bins)
        print("    prof:", " ".join("%s:%.3f-%.3f"%(k,min(bins[k]),max(bins[k])) for k in ts if k<=L+0.03)[:600])
json.dump(data, open(os.path.join(OUT,'hand_geom.json'),'w'), indent=1)
print("GEOM DUMP DONE")
