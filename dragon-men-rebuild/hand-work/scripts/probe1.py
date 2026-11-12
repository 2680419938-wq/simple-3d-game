
import bpy, json, os
from collections import defaultdict
OUT = r"D:\ai\建模\dragon-men-rebuild\hand-work\verify"
os.makedirs(OUT, exist_ok=True)
arm = bpy.data.objects.get("DragonMan_Rig")
bones = {b.name: b for b in arm.data.bones}
names = [n for n in bones if any(k in n for k in ("Thumb","Index","Middle","Ring","Pinky"))]
print("FINGER BONES:", len(names))
for nm in sorted(names):
    b = bones[nm]
    print("  %-30s head=%s tail=%s len=%.5f parent=%s" % (nm,
        tuple(round(v,5) for v in b.head_local), tuple(round(v,5) for v in b.tail_local), b.length, b.parent.name if b.parent else None))

body = bpy.data.objects.get("DragonMan_Body")
me = body.data
print("BODY verts", len(me.vertices), "polys", len(me.polygons), "tris", sum(len(p.vertices)-2 for p in me.polygons))
print("MATS", [m.name if m else None for m in me.materials], "UV", [u.name for u in me.uv_layers], "VG", len(body.vertex_groups))
n = len(me.vertices); parent=list(range(n))
def find(a):
    while parent[a]!=a:
        parent[a]=parent[parent[a]]; a=parent[a]
    return a
def union(a,b):
    ra,rb=find(a),find(b)
    if ra!=rb: parent[ra]=rb
for e in me.edges: union(e.vertices[0], e.vertices[1])
isl=defaultdict(list)
for i in range(n): isl[find(i)].append(i)
print("ISLANDS:", len(isl))
gname={g.index:g.name for g in body.vertex_groups}
dom=[None]*n
for v in me.vertices:
    bw=-1
    for ge in v.groups:
        if ge.weight>bw: bw=ge.weight; dom[v.index]=gname[ge.group]
sizes=sorted(((len(vs),r) for r,vs in isl.items()), reverse=True)
print("TOP ISLANDS:")
for sz,r in sizes[:12]:
    ds=defaultdict(int)
    for v in isl[r]: ds[dom[v]]+=1
    print("  size=%d doms=%s" % (sz, sorted(ds.items(), key=lambda x:-x[1])[:5]))
handisl=[]
for sz,r in sizes:
    ds=set(dom[v] for v in isl[r])
    if any(x and "Hand" in x for x in ds): handisl.append((sz,r,sorted(ds)))
print("HAND islands:", len(handisl))
for sz,r,ds in handisl:
    print("  size=%d doms=%s bbox_min=%s bbox_max=%s" % (sz, ds[:8],
        tuple(round(min(me.vertices[v].co[i] for v in isl[r]),4) for i in range(3)),
        tuple(round(max(me.vertices[v].co[i] for v in isl[r]),4) for i in range(3))))
# finger-group weighted vert counts per island for the big palm island
