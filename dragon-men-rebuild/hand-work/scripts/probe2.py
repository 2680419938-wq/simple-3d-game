
import bpy, os, json
from collections import defaultdict
from mathutils import Vector
OUT = r"D:\ai\建模\dragon-men-rebuild\hand-work"
arm = bpy.data.objects["DragonMan_Rig"]; body = bpy.data.objects["DragonMan_Body"]
for o in (arm, body, bpy.data.objects["DragonMan_Foot.L"], bpy.data.objects["DragonMan_Foot.R"]):
    print("OBJ %-22s loc=%s rot=%s scale=%s" % (o.name, tuple(round(v,4) for v in o.location), tuple(round(v,4) for v in o.rotation_euler), tuple(round(v,4) for v in o.scale)))
print("BODY matrix_world:", [round(v,5) for row in body.matrix_world for v in row])
print("ARM  matrix_world:", [round(v,5) for row in arm.matrix_world for v in row])

me = body.data
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
# palm island containing LeftHand dominant 508
gname={g.index:g.name for g in body.vertex_groups}
dom=[None]*n; ninf=[0]*n
for v in me.vertices:
    bw=-1; ninf[v.index]=len([g for g in v.groups if g.weight>1e-6])
    for ge in v.groups:
        if ge.weight>bw: bw=ge.weight; dom[v.index]=gname[ge.group]
palm=None
for r,vs in isl.items():
    c=sum(1 for v in vs if dom[v]=="mixamorig:LeftHand")
    if c==508: palm=r
print("palm island verts", len(isl[palm]))
MW = body.matrix_world
for side in ("Left","Right"):
    print("=== %s hand ===" % side)
    for f in ("Thumb","Index","Middle","Ring","Pinky"):
        for k in (1,2,3):
            bn="mixamorig:%sHand%s%d"%(side,f,k)
            vs=[v for v in isl[palm] if dom[v]==bn]
            if not vs: print("  %-28s NO VERTS"%bn); continue
            co=[MW@me.vertices[v].co for v in vs]
            multi=sum(1 for v in vs if ninf[v]>1)
            ax=(arm.matrix_world@arm.data.bones[bn].tail_local)-(arm.matrix_world@arm.data.bones[bn].head_local)
            print("  %-28s n=%3d multi=%3d centroidW=%s radialmax=%.4f axlen=%.4f" % (bn,len(vs),multi,
              tuple(round(v,4) for v in (sum(co,Vector())/len(co))), 0.0, ax.length))
# check bones present for Pinky
print("PINKY bones:", [b.name for b in arm.data.bones if "Pinky" in b.name])
# overall weight stats on palm island
mult = defaultdict(int)
for v in isl[palm]: mult[ninf[v]]+=1
print("palm island influence-count histogram:", dict(sorted(mult.items())))
