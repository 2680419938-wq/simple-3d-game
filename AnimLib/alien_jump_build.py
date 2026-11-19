
# -*- coding: utf-8 -*-
import bpy, math, os
from mathutils import Matrix, Vector
FBX  = r"D:/浏览器·/Jumping.fbx"
SRC  = r"D:/ai/建模/异形/Alien_Walk_2k.glb"
OUT  = r"D:/ai/建模/dragon-man-final/Alien_Walk_Jump_2k.glb"
M = {
 'Hips':'CC_Base_Hip_02','Spine':'CC_Base_Waist_033','Spine1':'CC_Base_Spine01_034','Spine2':'CC_Base_Spine02_035',
 'Neck':'CC_Base_NeckTwist01_036','Head':'CC_Base_Head_038',
 'LeftShoulder':'CC_Base_L_Clavicle_049','LeftArm':'CC_Base_L_Upperarm_050','LeftForeArm':'CC_Base_L_Forearm_051','LeftHand':'CC_Base_L_Hand_055',
 'RightShoulder':'CC_Base_R_Clavicle_074','RightArm':'CC_Base_R_Upperarm_075','RightForeArm':'CC_Base_R_Forearm_076','RightHand':'CC_Base_R_Hand_080',
 'LeftUpLeg':'CC_Base_L_Thigh_04','LeftLeg':'CC_Base_L_Calf_05','LeftFoot':'CC_Base_L_Foot_06','LeftToeBase':'CC_Base_L_ToeBase_08',
 'RightUpLeg':'CC_Base_R_Thigh_00','RightLeg':'CC_Base_R_Calf_019','RightFoot':'CC_Base_R_Foot_021','RightToeBase':'CC_Base_R_ToeBase_022',
}
def find(p, ex=()):
    for o in bpy.data.objects:
        if o.type=='ARMATURE' and o not in ex and any(b.name.startswith(p) for b in o.data.bones): return o
def resolve(cc, mix):
    ccb={b.name for b in cc.data.bones}; mixb={b.name for b in mix.data.bones}; out=[]
    for mk, ck in M.items():
        mb=None
        for c in ('mixamorig:'+mk, 'mixamorig_'+mk, mk, 'mixamorig'+mk):
            if c in mixb: mb=mix.data.bones[c]; break
        if mb is None: continue
        if ck in ccb: out.append((cc.data.bones[ck], mb)); continue
        base=ck.rsplit('_',1)[0] if ck.endswith('_') else ck
        h=[n for n in ccb if n.startswith(base) and '_scaleCompensation' not in n]
        if len(h)==1: out.append((cc.data.bones[h[0]], mb))
    return out
def depth(b):
    d=0
    while b.parent: d+=1; b=b.parent
    return d
def body_minz():
    dg=bpy.context.evaluated_depsgraph_get(); mn=1e9
    for o in bpy.data.objects:
        if o.type!='MESH': continue
        ev=o.evaluated_get(dg); me=ev.to_mesh(); mw=o.matrix_world
        for v in me.vertices:
            z=(mw@v.co).z
            if z<mn: mn=z
        ev.to_mesh_clear()
    return mn

bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
bpy.ops.import_scene.fbx(filepath=FBX)
mix=find('mixamorig')
jact=[a for a in bpy.data.actions][0]
bpy.ops.import_scene.gltf(filepath=SRC)
cc=find('CC_Base_',(mix,))
print('CC', cc.name, len(cc.data.bones))
for o in list(bpy.data.objects):
    if o.name.startswith('Icosphere'): bpy.data.objects.remove(o, do_unlink=True)
pairs=resolve(cc, mix); pair_by={cb.name: mb for cb, mb in pairs}
MWM=mix.matrix_world.copy(); MWC=cc.matrix_world.copy(); MWCI=MWC.inverted()
ratio=(MWC@cc.data.bones['CC_Base_Hip_02'].matrix_local.translation).length / (MWM@mix.data.bones['mixamorig:Hips'].matrix_local.translation).length
mix.animation_data_create(); mix.animation_data.action=jact
cc.animation_data_create()
jp=bpy.data.actions.new('Jump'); jp.use_fake_user=True
cc.animation_data.action=jp
for pb in cc.pose.bones: pb.rotation_mode='QUATERNION'; pb.matrix_basis=Matrix.Identity(4)
f0,f1=int(jact.frame_range[0]), int(jact.frame_range[1])
allb=sorted(cc.data.bones, key=depth)
for f in range(f0,f1+1):
    sc.frame_set(f)
    P={}
    for cb in allb:
        R_c=cb.matrix_local
        ref=(P[cb.parent.name]@cb.parent.matrix_local.inverted()@R_c) if cb.parent else R_c
        mb=pair_by.get(cb.name)
        if mb is None:
            P[cb.name]=ref; continue
        P_m=MWM@mix.pose.bones[mb.name].matrix
        D=P_m@(MWM@mb.matrix_local).inverted()
        target=(MWCI@D@MWC)@R_c
        if cb.name=='CC_Base_Hip_02':
            t_w=P_m.translation-(MWM@mb.matrix_local).translation
            target.translation=R_c.translation+(MWCI.to_3x3()@t_w)*ratio
        B=ref.inverted()@target; P[cb.name]=target
        loc,rot,_=B.decompose(); pc=cc.pose.bones[cb.name]; pc.rotation_quaternion=rot
        if cb.name=='CC_Base_Hip_02': pc.location=loc; pc.keyframe_insert('location', frame=f)
        pc.keyframe_insert('rotation_quaternion', frame=f)
print('RETARGET %d..%d'%(f0,f1))
# ---- remove mixamo skeleton so it is not exported ----
for o in list(bpy.data.objects):
    if o is mix: continue
    if o.type in ('MESH',) and not any(m.type=='ARMATURE' for m in o.modifiers): pass
bpy.data.objects.remove(mix, do_unlink=True)
for a in list(bpy.data.actions):
    if a is not jp and a.name not in ('Walk','Idle'):
        print('DEL action', a.name); bpy.data.actions.remove(a)
print('OBJS', [o.name for o in bpy.data.objects])
# ---- ground clamp (proper local axis) ----
try: cc.animation_data.action_slot = jp.slots[0]
except Exception as e: print('SLOT1', e)
hp=cc.pose.bones['CC_Base_Hip_02']
M3=(cc.matrix_world.to_3x3() @ cc.data.bones['CC_Base_Hip_02'].matrix_local.to_3x3()).inverted()
print('AXIS world+Z -> local', tuple(round(v,3) for v in (M3 @ Vector((0,0,1)))))
lifted=0; maxneed=0.0
for f in range(f0,f1+1):
    sc.frame_set(f)
    mn=body_minz()
    need=max(0.0, 0.002-mn)
    if need>1e-6:
        lifted+=1; maxneed=max(maxneed,need)
        hp.location = hp.location + (M3 @ Vector((0,0,need)))
        hp.keyframe_insert('location', frame=f)
    else: maxneed=max(maxneed,need)
print('CLAMP lifted %d frames, max %.4f' % (lifted, maxneed))
try: cc.animation_data.action_slot = jp.slots[0]
except Exception as e: print('SLOT2', e)
mn2=1e9; mnf=None
for f in range(f0,f1+1):
    sc.frame_set(f); m=body_minz()
    if m<mn2: mn2, mnf = m, f
print('POST minz %.4f at F%d' % (mn2, mnf))
sc.render.fps=24
for a in bpy.data.actions: a.use_fake_user=True
print('ACTIONS', [(a.name, tuple(round(x,1) for x in a.frame_range)) for a in bpy.data.actions])
cc.animation_data.action=None
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
    export_image_format='WEBP', export_image_quality=80,
    export_animations=True, export_animation_mode='ACTIONS',
    export_skins=True, export_yup=True, export_apply=False,
    export_bake_animation=False, export_optimize_animation_size=False)
print('EXPORTED', OUT, os.path.getsize(OUT))
