# -*- coding: utf-8 -*-
import bpy, sys
import numpy as np
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\walk-work\scripts')
import walklib as W
bpy.ops.wm.open_mainfile(filepath=r'D:\ai\建模\dragon-men-rebuild\armor-work\DragonMan_Armor.blend')
sc = bpy.context.scene; arm = bpy.data.objects['DragonMan_Rig']
def pr(*a): print('[P]',*a); sys.stdout.flush()
meshes = W.char_meshes()
arm.animation_data.action = None
W.reset_pose(arm)
pr('REST min z %.4f' % min(float(W.evworld(o)[:,2].min()) for o in meshes))
for an in ('Idle_Lively','Walk'):
    arm.animation_data.action = bpy.data.actions[an]
    for f in (1,3,7,17,25):
        sc.frame_set(0); sc.frame_set(f); bpy.context.view_layer.update()
        zs = [float(W.evworld(o)[:,2].min()) for o in meshes]
        pr('%s f%02d min z %s' % (an, f, [round(z,4) for z in zs]))
