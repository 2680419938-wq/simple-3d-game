import bpy, bmesh, math, importlib, numpy as np
from mathutils import Vector, Matrix
EXT=r'C:/Users/26804/AppData/Roaming/Blender Foundation/Blender/5.3/extensions/user_default'
import sys; sys.path.insert(0,EXT)
bpy.ops.preferences.addon_enable(module='bl_ext.user_default.mpfb')
HS=importlib.import_module('bl_ext.user_default.mpfb.services.humanservice').HumanService
SRC=r'D:/ai/建模/dragon-men-rebuild/skin-work/mpfb_male.blend'
V2=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody/v2.blend'
PARTS=r'D:/ai/建模/dragon-men-rebuild/skin-work/armor_parts.blend'
OUT=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody'
bpy.ops.wm.open_mainfile(filepath=SRC)
for o in list(bpy.data.objects):
    if o.name not in ('Human',): bpy.data.objects.remove(o, do_unlink=True)
human=bpy.data.objects['Human']
rig=HS.add_builtin_rig(human,'default')
print('RIG',rig.name,len(rig.data.bones))
MW=human.matrix_world.copy(); M=human.data
bm=bmesh.new(); bm.from_mesh(M)
kill=[v for v in bm.verts if (MW@v.co).z>1.42]
bmesh.ops.delete(bm, geom=kill, context='VERTS')
bm.to_mesh(M); bm.free()
print('BODY',len(M.vertices))
W=[MW@v.co for v in M.vertices]

def mat(name,col,metal,rough):
    m=bpy.data.materials.new(name); m.use_nodes=True
    b=[n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'][0]
    b.inputs['Base Color'].default_value=(*col,1)
    b.inputs['Metallic'].default_value=metal; b.inputs['Roughness'].default_value=rough
    return m
def scalemat():
    m=bpy.data.materials.new('DragonScale'); m.use_nodes=True
    nt=m.node_tree; b=[n for n in nt.nodes if n.type=='BSDF_PRINCIPLED'][0]
    b.inputs['Metallic'].default_value=0.35; b.inputs['Roughness'].default_value=0.38
    tc=nt.nodes.new('ShaderNodeTexCoord')
    vo=nt.nodes.new('ShaderNodeTexVoronoi'); vo.feature='DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value=30
    ra=nt.nodes.new('ShaderNodeValToRGB')
    ra.color_ramp.elements[0].position=0.0; ra.color_ramp.elements[0].color=(0.015,0.008,0.04,1)
    ra.color_ramp.elements[1].position=0.055; ra.color_ramp.elements[1].color=(0.10,0.055,0.21,1)
    e=ra.color_ramp.elements.new(0.20); e.color=(0.17,0.10,0.32,1)
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
    nt.links.new(vo.outputs['Distance'], ra.inputs['Fac'])
    nt.links.new(ra.outputs['Color'], b.inputs['Base Color'])
    return m
PLATE=mat('ArmorPlate',(0.022,0.032,0.095),0.70,0.28)
TRIM =mat('ArmorTrim',(0.78,0.38,0.10),0.95,0.26)
BODY =mat('BodyBase',(0.62,0.58,0.52),0.0,0.60)
SCALE=scalemat()
CLAW =mat('ClawGold',(0.72,0.55,0.22),1.0,0.18)
NB=48
def fit_ring(z,xmax=0.24,half=0.03):
    bins=[[] for _ in range(NB)]
    for v in W:
        if abs(v.z-z)>half or abs(v.x)>xmax: continue
        a=math.atan2(v.y,v.x); bins[int((a+math.pi)/(2*math.pi)*NB)%NB].append(math.hypot(v.x,v.y))
    out=[max(b) if b else None for b in bins]
    for i in range(NB):
        if out[i] is None:
            for dd in range(1,NB):
                a=out[(i-dd)%NB]; b=out[(i+dd)%NB]
                if a is not None or b is not None:
                    vals=[x for x in (a,b) if x is not None]; out[i]=sum(vals)/len(vals); break
    out=[x or 0.1 for x in out]
    return [(out[(i-1)%NB]+2*out[i]+out[(i+1)%NB])/4 for i in range(NB)]
def attach(o, groups, bind=True):
    for g,fn in groups.items():
        vg=o.vertex_groups.get(g) or o.vertex_groups.new(name=g)
        for v in o.data.vertices:
            w=fn(o.matrix_world@v.co)
            if w>0.001: vg.add([v.index],min(1.0,w),'REPLACE')
    if bind:
        o.parent=rig; o.parent_type='OBJECT'
        md=o.modifiers.new('Armature','ARMATURE'); md.object=rig
def shell(name,keep,thick,idxskip=None):
    o=human.copy(); o.data=human.data.copy(); o.name=name
    o.modifiers.clear(); o.shape_key_clear()
    for g in list(human.vertex_groups): o.vertex_groups.new(name=g.name)
    bpy.context.scene.collection.objects.link(o)
    bm=bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if (not keep(MW@f.calc_center_median())) or (idxskip is not None and f.index in idxskip)], context='FACES')
    bm.to_mesh(o.data); bm.free()
    o.matrix_world=MW.copy()
    o.data.materials.clear(); o.data.materials.append(PLATE); o.data.materials.append(TRIM)
    for p in o.data.polygons: p.material_index=0; p.use_smooth=True
    md=o.modifiers.new('S','SOLIDIFY'); md.thickness=thick; md.offset=1; md.use_rim=True; md.material_offset_rim=1
    bpy.context.view_layer.objects.active=o; bpy.ops.object.modifier_apply(modifier='S')
    attach(o,{},bind=True)
    print('  %-12s v=%d g=%d'%(name,len(o.data.vertices),len(o.vertex_groups))); return o
def loft(name,zs,rows,thick,m,groups,mask=None):
    bmx=bmesh.new(); rr=[]
    for z,rs in zip(zs,rows):
        rr.append([bmx.verts.new((math.cos(2*math.pi*i/NB)*rs[i], math.sin(2*math.pi*i/NB)*rs[i], z)) for i in range(NB)])
    for j in range(len(rr)-1):
        for i in range(NB):
            if mask is not None and not mask(i): continue
            bmx.faces.new((rr[j][i],rr[j][(i+1)%NB],rr[j+1][(i+1)%NB],rr[j+1][i]))
    me=bpy.data.meshes.new(name); bmx.to_mesh(me); bmx.free()
    o=bpy.data.objects.new(name,me); bpy.context.scene.collection.objects.link(o)
    me.materials.append(m)
    for p in me.polygons: p.use_smooth=True
    md=o.modifiers.new('S','SOLIDIFY'); md.thickness=thick; md.offset=0
    bpy.context.view_layer.objects.active=o; bpy.ops.object.modifier_apply(modifier='S')
    attach(o,groups); return o
def cone(name,base,tip,r0,SEG,m,groups):
    b=Vector(base); t=Vector(tip); ax=(t-b).normalized()
    up=Vector((0,0,1)) if abs(ax.z)<0.9 else Vector((0,1,0))
    u=ax.cross(up).normalized(); v=ax.cross(u).normalized()
    bmx=bmesh.new()
    ring=[bmx.verts.new(b+u*(math.cos(2*math.pi*i/SEG)*r0)+v*(math.sin(2*math.pi*i/SEG)*r0)) for i in range(SEG)]
    mid=[bmx.verts.new(b+u*(math.cos(2*math.pi*i/SEG)*r0*0.55)+v*(math.sin(2*math.pi*i/SEG)*r0*0.55)+ax*((t-b).length*0.55)) for i in range(SEG)]
    tipv=bmx.verts.new(t)
    bmx.faces.new(list(reversed(ring)))
    for i in range(SEG):
        bmx.faces.new((ring[i],ring[(i+1)%SEG],mid[(i+1)%SEG],mid[i]))
        bmx.faces.new((mid[i],mid[(i+1)%SEG],tipv))
    me=bpy.data.meshes.new(name); bmx.to_mesh(me); bmx.free()
    o=bpy.data.objects.new(name,me); bpy.context.scene.collection.objects.link(o)
    me.materials.append(m)
    for p in me.polygons: p.use_smooth=True
    attach(o,groups); return o
AW={}
_ag={g.index for g in human.vertex_groups if g.name.startswith(('upperarm','lowerarm','hand','clavicle','shoulder'))}
for v in human.data.vertices:
    s=0.0
    for ge in v.groups:
        if ge.group in _ag: s=max(s,ge.weight)
    AW[v.index]=s
ARMF={p.index for p in human.data.polygons if max(AW.get(i,0.0) for i in p.vertices)>0.35}
print('ARMF faces',len(ARMF))
def chest(c): return 0.95<=c.z<=1.28 and abs(c.x)<=0.27
def sd(p,a,b):
    ab=b-a; t=max(0,min(1,(p-a).dot(ab)/ab.length_squared)); return (p-(a+ab*t)).length
def tt(p,a,b):
    ab=b-a; return (p-a).dot(ab)/ab.length_squared
SL=Vector((0.205,-0.02,1.262)); SR=Vector((-0.205,-0.02,1.262))
BLA=Vector((0.378,-0.132,1.058)); BLB=Vector((0.452,-0.183,0.998))
BRA=Vector((-0.378,-0.132,1.058)); BRB=Vector((-0.452,-0.183,0.998))
def tor(c): return math.hypot(c.x,c.y)<0.205
shell('AR_chestA',lambda c:0.950<=c.z<=1.050 and tor(c),0.020)
shell('AR_chestB',lambda c:1.065<=c.z<=1.155 and tor(c),0.020)
shell('AR_chestC',lambda c:1.170<=c.z<=1.280 and tor(c),0.020)
shell('AR_pauldronLU',lambda c:(c-SL).length<0.118 and c.z>=1.255,0.022)
shell('AR_pauldronLD',lambda c:(c-SL).length<0.130 and 1.198<=c.z<1.243,0.020)
shell('AR_pauldronRU',lambda c:(c-SR).length<0.118 and c.z>=1.255,0.022)
shell('AR_pauldronRD',lambda c:(c-SR).length<0.130 and 1.198<=c.z<1.243,0.020)
shell('AR_bracerLA',lambda c:0.00<=tt(c,BLA,BLB)<=0.44 and sd(c,BLA,BLB)<0.060,0.016)
shell('AR_bracerLB',lambda c:0.52<=tt(c,BLA,BLB)<=1.02 and sd(c,BLA,BLB)<0.060,0.016)
shell('AR_bracerRA',lambda c:0.00<=tt(c,BRA,BRB)<=0.44 and sd(c,BRA,BRB)<0.060,0.016)
shell('AR_bracerRB',lambda c:0.52<=tt(c,BRA,BRB)<=1.02 and sd(c,BRA,BRB)<0.060,0.016)
PEL={'pelvis.L':lambda p:1.0 if p.x>=0 else 0.0,'pelvis.R':lambda p:1.0 if p.x<0 else 0.0}
r_wai=fit_ring(0.955,0.24); r_sk=fit_ring(0.905,0.24)
loft('AR_belt',[0.935,0.975],[r_wai,r_wai],0.016,TRIM,PEL)
r_rib=[r_sk[i]*(1.0+0.030*math.cos(10*2*math.pi*i/NB)) for i in range(NB)]
t1=[[min(r*k,0.29) for r in r_rib] for k in [1.04,1.07,1.09]]
t2=[[min(r*k,0.31) for r in r_rib] for k in [1.11,1.15,1.18]]
mk1=lambda i: i%12!=0
mk2=lambda i: i%12!=6
loft('AR_skirt1',[0.915,0.850,0.788],t1,0.018,PLATE,PEL,mk1)
loft('AR_skirt2',[0.774,0.722,0.672],t2,0.018,PLATE,PEL,mk2)
hem=[min(r*1.21,0.34) for r in r_rib]
loft('AR_hem',[0.628,0.668],[hem,hem],0.014,TRIM,PEL)
feet=[v for v in W if v.z<0.07]
from mathutils import kdtree
for side,sx in (('L',1),('R',-1)):
    bn='foot.'+side
    f=[v for v in feet if (v.x*sx)>0.02]
    kd=kdtree.KDTree(len(f))
    for i,v in enumerate(f): kd.insert(v,i)
    kd.balance()
    fy=min(v.y for v in f); fx=[v.x for v in f]; x0,x1=min(fx),max(fx)
    for k in range(4):
        tx=x0+(x1-x0)*(0.15+0.23*k)
        co,idx,dist=kd.find((tx,fy+0.03,0.02))
        b=Vector(co)+Vector((0,0.012,0.004))
        d=Vector(((co.x-(x0+x1)/2)*0.25,-0.82,-0.30)).normalized()
        cone('CL_%s%d'%(side,k),b,b+d*0.075,0.016,10,CLAW,{bn:lambda p:1.0})
# head
with bpy.data.libraries.load(V2, link=False) as (s,d):
    d.objects=[n for n in s.objects if n=='DragonHead']
hd=bpy.data.objects['DragonHead']; bpy.context.scene.collection.objects.link(hd)
attach(hd,{'head':lambda p:1.0})
# tail
with bpy.data.libraries.load(PARTS, link=False) as (s,d):
    d.objects=[n for n in s.objects if n.startswith('P001') or n.startswith('P000')]
tails=[o for o in bpy.data.objects if o.name.startswith('P00')]
allv=np.vstack([np.array([[v.co.x,v.co.y,v.co.z] for v in o.data.vertices]) for o in tails])
c0=allv.mean(0); X=allv-c0
u,s2,vt=np.linalg.svd(X,full_matrices=False); axis=vt[0]; proj=X@axis
if allv[proj.argmin()][1]>allv[proj.argmax()][1]: axis=-axis; proj=-proj
base=allv[proj.argmin()]
tgt=Vector((0.34,0.70,-0.62)).normalized()
rot=Vector(axis).rotation_difference(tgt).to_matrix().to_4x4()
T=Matrix.Translation(Vector((0.04,0.15,0.80))) @ rot @ Matrix.Scale(0.52,4) @ Matrix.Translation(-Vector(base))
_ct=T @ Vector(allv.mean(0))
print('TAIL centroid after T', tuple(round(x,3) for x in _ct))
if _ct.y < 0.24:
    _RZ=Matrix.Rotation(math.pi,4,'Z'); _B=Vector((0.04,0.15,0.80))
    T=Matrix.Translation(_B) @ _RZ @ Matrix.Translation(-_B) @ T
    print('TAIL flipped 180 about Z')
for o in tails:
    o.matrix_world=T; bpy.context.scene.collection.objects.link(o)
    o.data.transform(T); o.matrix_world=Matrix.Identity(4)
tv=np.vstack([np.array([[v.co.x,v.co.y,v.co.z] for v in o.data.vertices]) for o in tails])
tb=tv.mean(0); Y=tv-tb
u2,s3,vt2=np.linalg.svd(Y,full_matrices=False); ax2=Vector(vt2[0])
pr=Y@np.array(ax2)
if tv[pr.argmin()][2]<tv[pr.argmax()][2]: ax2=-ax2; pr=-pr
p0=Vector(tv[pr.argmin()]); p1=Vector(tv[pr.argmax()])
L=pr.max()-pr.min(); pmin,pmax=pr.min(),pr.max()
bpy.context.view_layer.objects.active=rig; bpy.ops.object.mode_set(mode='EDIT')
prev=None
for i in range(3):
    eb=rig.data.edit_bones.new('tail0%d'%(i+1))
    eb.head=p0+ax2*(L*i/3.0); eb.tail=p0+ax2*(L*(i+1)/3.0)
    eb.parent=prev if prev else rig.data.edit_bones['pelvis.L']
    prev=eb
bpy.ops.object.mode_set(mode='OBJECT')
print('TAILBONES',[b.name for b in rig.data.bones if b.name.startswith('tail')], p0, ax2, L)
for o in tails:
    for i in range(1,4): o.vertex_groups.new(name='tail0%d'%i)
    for v in o.data.vertices:
        t=(np.array(v.co)[None,:]@np.array(ax2))[0]
        f=max(0.0,min(2.999,(t-pmin)/max(1e-6,(pmax-pmin))*3.0))
        i=int(f); w=f-i
        o.vertex_groups['tail0%d'%(i+1)].add([v.index],1-w,'REPLACE')
        if i<2: o.vertex_groups['tail0%d'%(i+2)].add([v.index],w,'REPLACE')
    o.parent=rig; md=o.modifiers.new('Armature','ARMATURE'); md.object=rig
human.data.materials.clear(); human.data.materials.append(BODY); human.data.materials.append(SCALE)
for p in human.data.polygons:
    c=MW@p.center
    p.material_index=1 if (c.z<0.94 or abs(c.x)>0.27) else 0
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/char_rig.blend')
print('DONE')