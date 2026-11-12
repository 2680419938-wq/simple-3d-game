
# -*- coding: utf-8 -*-
import bpy, sys, os
from mathutils import Vector
argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
opt={argv[i].lstrip('-'):argv[i+1] for i in range(0,len(argv)-1,2)}
SRC=opt['src']; OUT=opt['out']; K=float(opt.get('k','1.7'))
bpy.ops.wm.open_mainfile(filepath=SRC)
arm=bpy.data.objects['DragonMan_Rig']; MW=arm.matrix_world; MWi=MW.inverted()
def bn(n):
    for c in (n,'mixamorig:'+n,n.replace('mixamorig:','')):
        if c in arm.data.bones: return c
    raise KeyError(n)
UP={s:bn('LeftUpLeg' if s=='L' else 'RightUpLeg') for s in 'LR'}
LO={s:bn('LeftLeg' if s=='L' else 'RightLeg') for s in 'LR'}
FO={s:bn('LeftFoot' if s=='L' else 'RightFoot') for s in 'LR'}
def wpos(name,which='head'):
    b=arm.data.bones[name]
    return MW @ (b.head_local if which=='head' else b.tail_local)
ZA={s:wpos(FO[s],'head').z for s in 'LR'}
ZH={s:wpos(UP[s],'head').z for s in 'LR'}
D={s:(ZH[s]-ZA[s])*(K-1.0) for s in 'LR'}
STEER=set(UP.values())|set(LO.values())
FOOT=set()
for s in 'LR':
    FOOT.add(FO[s]); FOOT.add(bn('LeftToeBase' if s=='L' else 'RightToeBase'))
print('K %.3f / legs L %.3f->%.3f  R %.3f->%.3f'%(K,ZH['L']-ZA['L'],(ZH['L']-ZA['L'])*K,ZH['R']-ZA['R'],(ZH['R']-ZA['R'])*K))
for ob in [o for o in bpy.data.objects if o.type=='MESH']:
    if ob.name.startswith('WGT_'): continue
    me=ob.data; M=ob.matrix_world; Mi=M.inverted()
    gname={vg.index:vg.name for vg in ob.vertex_groups}
    nleg=nfoot=nbody=0
    for v in me.vertices:
        wl={'L':0.0,'R':0.0}; wf=0.0
        for g in v.groups:
            nm=gname.get(g.group,'')
            if nm in STEER:
                wl['L' if 'Left' in nm else 'R']+=g.weight
            elif nm in FOOT or ('Foot' in nm) or ('Toe' in nm):
                wf+=g.weight
        s='L' if wl['L']>=wl['R'] else 'R'
        wleg=wl[s]
        wsum=min(1.0,wleg+wf); wbody=1.0-wsum
        if wsum<=1e-6:
            dz=(D['L']+D['R'])*0.5
            p=M@v.co; v.co=Mi@Vector((p.x,p.y,p.z+dz)); nbody+=1; continue
        p=M@v.co
        zst=ZA[s]+(p.z-ZA[s])*K
        znew=wleg*zst+wf*p.z+wbody*(p.z+D[s])
        v.co=Mi@Vector((p.x,p.y,znew))
        if wleg>wf: nleg+=1
        else: nfoot+=1
    me.update()
    print('XF %-16s leg %5d foot %5d body %5d'%(ob.name,nleg,nfoot,nbody))
bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
eb=arm.data.edit_bones
for b in eb:
    nm=b.name; s=None
    if nm in (UP['L'],LO['L']): s='L'
    elif nm in (UP['R'],LO['R']): s='R'
    if s:
        for attr in ('head','tail'):
            p=MW@getattr(b,attr); setattr(b,attr, MWi@Vector((p.x,p.y,ZA[s]+(p.z-ZA[s])*K)))
    elif nm in FOOT or 'Toe' in nm:
        pass
    else:
        dz=(D['L']+D['R'])*0.5
        for attr in ('head','tail'):
            p=MW@getattr(b,attr); setattr(b,attr, MWi@Vector((p.x,p.y,p.z+dz)))
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()
for s in 'LR':
    print('BONE %s hip %.3f knee %.3f ankle %.3f'%(s,wpos(UP[s]).z,wpos(LO[s]).z,wpos(FO[s]).z))
MESH=[o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith('WGT_')]
def minz():
    dg=bpy.context.evaluated_depsgraph_get(); mz=1e9
    for o in MESH:
        ev=o.evaluated_get(dg); m=ev.to_mesh()
        for v in m.vertices:
            z=(o.matrix_world@v.co).z
            if z<mz: mz=z
        ev.to_mesh_clear()
    return mz
if arm.animation_data is None: arm.animation_data_create()
gmin=1e9
for a in bpy.data.actions:
    arm.animation_data.action=a
    try: arm.animation_data.action_slot=a.slots[0]
    except Exception: pass
    f0,f1=int(a.frame_range[0]),int(a.frame_range[1])
    for fr in range(f0,f1+1,max(1,(f1-f0)//10)):
        bpy.context.scene.frame_set(fr); gmin=min(gmin,minz())
arm.animation_data.action=None
for pb in arm.pose.bones:
    pb.matrix_basis=__import__('mathutils').Matrix.Identity(4)
bpy.context.scene.frame_set(0)
bpy.context.view_layer.update()
print('GMIN %.4f'%gmin)
DZ=-gmin
if abs(DZ)>1e-5:
    for ob in MESH:
        Mi=ob.matrix_world.inverted()
        ob.data.transform(__import__('mathutils').Matrix.Translation(Mi.to_3x3()@Vector((0,0,DZ))))
    bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='EDIT')
    for b in arm.data.edit_bones:
        b.head.z+=DZ; b.tail.z+=DZ
    bpy.ops.object.mode_set(mode='OBJECT'); bpy.context.view_layer.update()
print('GROUNDED by %.4f -> minz %.4f'%(DZ,minz()))
top=max((o.matrix_world@v.co).z for o in MESH for v in o.data.vertices)
for s in 'LR': print('FINAL %s hip %.3f knee %.3f'%(s,wpos(UP[s]).z,wpos(LO[s]).z))
print('FINAL top %.3f  legRatio %.3f'%(top,(wpos(UP['L']).z)/top))
bpy.ops.wm.save_as_mainfile(filepath=OUT); print('SAVED',OUT)