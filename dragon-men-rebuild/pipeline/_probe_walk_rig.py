# -*- coding: utf-8 -*-
"""Probe: rig geometry + shell-gap vs knee-bend relationship (no writes)."""
import bpy, math, json
import numpy as np
from mathutils import Matrix, Vector

BLEND = r'D:\ai\建模\dragon-men-rebuild\armor-work\DragonMan_Armor.blend'
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
print('[P] fps', sc.render.fps, 'scale', tuple(round(x,4) for x in arm.matrix_world.to_scale()))
print('[P] objects', [o.name for o in bpy.data.objects])
print('[P] bones', len(arm.data.bones))
print('[P] actions', [(a.name, tuple(round(x,1) for x in a.frame_range), a.use_fake_user) for a in bpy.data.actions])
B = arm.data.bones
for n in ['root','pelvis','spine','thigh.L','shin.L','foot.L','toe.01.L','thigh.R','shin.R','foot.R']:
    b = B.get(n)
    if b: print('[P] bone %-10s parent=%-10s head=%s tail=%s len=%.4f' % (n, b.parent.name if b.parent else '-', tuple(round(x,4) for x in b.head_local), tuple(round(x,4) for x in b.tail_local), b.length))
S = arm.matrix_world.to_scale().x
Lt = {s: B['thigh.'+s].length*S for s in 'LR'}
Ls = {s: B['shin.'+s].length*S for s in 'LR'}
print('[P] leg lengths thigh/shin/reach L %.4f/%.4f/%.4f  R %.4f/%.4f/%.4f' % (Lt['L'],Ls['L'],Lt['L']+Ls['L'],Lt['R'],Ls['R'],Lt['R']+Ls['R']))
print('[P] pelvis head z %.4f  ankle z L %.4f R %.4f  hip z L %.4f R %.4f' % (B['pelvis'].head_local.z*S, B['foot.L'].head_local.z*S, B['foot.R'].head_local.z*S, B['thigh.L'].head_local.z*S, B['thigh.R'].head_local.z*S))
# current walk: knee bend / pelvis z / foot pos per frame
act = bpy.data.actions.get('Walk')
ncon = sum(len(pb.constraints) for pb in arm.pose.bones)
print('[P] constraints', ncon, 'arm scale', S)
arm.animation_data.action = act
def goto(f):
    sc.frame_set(0); sc.frame_set(f); bpy.context.view_layer.update()
print('[P] walk frame, pelvis_z, knee bend L/R, foot world y/x')
for f in range(1,34):
    goto(f)
    pz = (arm.matrix_world @ arm.pose.bones['pelvis'].matrix).translation.z
    line=[]
    for s in 'LR':
        th = (arm.pose.bones['thigh.'+s].tail - arm.pose.bones['thigh.'+s].head)
        sh = (arm.pose.bones['shin.'+s].tail - arm.pose.bones['shin.'+s].head)
        line.append(math.degrees(th.angle(sh)))
    fz = (arm.matrix_world @ arm.pose.bones['foot.L'].matrix).translation
    print('[P] f%02d pelvis %.4f bendL %5.1f bendR %5.1f footL y%.4f z%.4f' % (f, pz, line[0], line[1], fz.y, fz.z))
