
# -*- coding: utf-8 -*-
import bpy, sys, math, bmesh
from mathutils import Vector
argv=sys.argv[sys.argv.index('--')+1:]
opt={argv[i].lstrip('-'):argv[i+1] for i in range(0,len(argv)-1,2)}
SRC=opt['src']; OUT=opt['out']
SEG=int(opt.get('seg','20')); NR=int(opt.get('rings','12')); EXT=float(opt.get('ext','0.06'))
bpy.ops.wm.open_mainfile(filepath=SRC)
arm=bpy.data.objects['DragonMan_Rig']; ob=bpy.data.objects['DragonMan_Body']
me=ob.data; M=ob.matrix_world; Mi=M.inverted(); MA=arm.matrix_world
def bn(n):
    for c in (n,'mixamorig:'+n,n.replace('mixamorig:','')):
        if c in arm.data.bones: return c
    raise KeyError(n)
def bh(n):
    b=arm.data.bones[bn(n)]; return MA@b.head_local, MA@b.tail_local
LEG={}
for s,up,lo,ft in (('L','LeftUpLeg','LeftLeg','LeftFoot'),('R','RightUpLeg','RightLeg','RightFoot')):
    H,_=bh(up); K,_=bh(lo); A,_=bh(ft)
    LEG[s]=(H.copy(),K.copy(),A.copy(),bn(up),bn(lo))
# --- locate 294v pale shells
n=len(me.vertices); par=list(range(n))
def find(a):
    while par[a]!=a: par[a]=par[par[a]]; a=par[a]
    return a
for e in me.edges:
    ra,rb=find(e.vertices[0]),find(e.vertices[1])
    if ra!=rb: par[rb]=ra
isl={}
for i in range(n): isl.setdefault(find(i),[]).append(i)
gname={vg.index:vg.name for vg in ob.vertex_groups}
kill=set()
for root,vs in isl.items():
    if len(vs)!=294: continue
    dom=None; best=0.0
    for i in vs[:24]:
        for g in me.vertices[i].groups:
            if g.weight>best: best=g.weight; dom=gname.get(g.group,'')
    if dom and 'UpLeg' in dom: kill.update(vs)
matidx=0
for p in me.polygons:
    if p.vertices[0] in kill: matidx=p.material_index; break
print('KILL',len(kill),'matidx',matidx)
bm=bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.verts[i] for i in sorted(kill)], context='VERTS')
bm.verts.ensure_lookup_table()
def lerptab(tab,t):
    for i in range(len(tab)-1):
        a,b=tab[i],tab[i+1]
        if a[0]<=t<=b[0]:
            k=(t-a[0])/max(1e-9,(b[0]-a[0])); return a[1]+(b[1]-a[1])*k
    return tab[-1][1]
PROF=[(0.00,0.142),(0.18,0.140),(0.42,0.130),(0.66,0.114),(0.85,0.102),(1.00,0.098),(1.10,0.092),(1.22,0.062)]
vrec=[]; frec=[]
for s,(H,K,A,bup,blo) in LEG.items():
    d=(K-H)
    path=[H+d*(i/(NR-1.0)) for i in range(NR)]
    dirK=(A-K).normalized()
    for i in range(1,4): path.append(K+dirK*(EXT*i/3.0))
    for _ in range(2):
        np=path[:]
        for i in range(1,len(path)-1): np[i]=(path[i-1]+path[i]*2.0+path[i+1])*0.25
        path=np
    rings=[]
    for i,p in enumerate(path):
        t=i/(len(path)-1.0)*1.22
        r=lerptab(PROF,t)
        nxt=path[min(i+1,len(path)-1)]; prv=path[max(i-1,0)]
        dv=(nxt-prv); dv.normalize()
        up=Vector((0,0,1))
        if abs(dv.dot(up))>0.95: up=Vector((0,1,0))
        x=dv.cross(up); x.normalize(); y=dv.cross(x); y.normalize()
        rings.append([p + x*(math.cos(2*math.pi*k/SEG)*r*0.92) + y*(math.sin(2*math.pi*k/SEG)*r*1.10) for k in range(SEG)])
    bv=[]
    for ring in rings:
        bv.append([bm.verts.new(Mi@p) for p in ring])
    bm.verts.ensure_lookup_table()
    for i in range(len(bv)-1):
        for k in range(SEG):
            k2=(k+1)%SEG
            f=bm.faces.new((bv[i][k],bv[i][k2],bv[i+1][k2],bv[i+1][k])); f.material_index=matidx
    f=bm.faces.new(tuple(reversed(bv[0]))); f.material_index=matidx
    f=bm.faces.new(tuple(bv[-1])); f.material_index=matidx
    for i,ring in enumerate(bv):
        t=i/(len(bv)-1.0)*1.22
        for v in ring: vrec.append((v,s,t))
bm.verts.index_update()
rec=[(tuple(round(c,6) for c in v.co),s,t) for v,s,t in vrec]
bm.to_mesh(me); bm.free(); me.update()
key={}
for i,v in enumerate(me.vertices):
    key.setdefault((round(v.co.x,6),round(v.co.y,6),round(v.co.z,6)),[]).append(i)
rec2=[]
for k,s,t in rec:
    hits=key.get(k,[])
    if hits: rec2.append((hits.pop(0),s,t))
print('MAPPED',len(rec2),'of',len(rec))
rec=rec2
def smooth(x): x=max(0.0,min(1.0,x)); return x*x*(3-2*x)
gup=[ob.vertex_groups.get(nm) or ob.vertex_groups.new(name=nm) for nm in (LEG['L'][3],LEG['R'][3],LEG['L'][4],LEG['R'][4])]
gmap={g.name:g for g in ob.vertex_groups}
for idx,s,t in rec:
    bup,blo=LEG[s][3],LEG[s][4]
    w=smooth((t-0.72)/0.40)   # 0 -> UpLeg, 1 -> Leg
    if w<0.999: gmap[bup].add([idx],1.0-w,'REPLACE')
    if w>0.001: gmap[blo].add([idx],w,'REPLACE')
for p in me.polygons: p.use_smooth=True
me.update()
print('NEWVERTS',len(rec),'TOTALV',len(me.vertices),'TOTALF',len(me.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT); print('SAVED',OUT)



