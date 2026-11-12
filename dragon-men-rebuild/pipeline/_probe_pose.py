# -*- coding: utf-8 -*-
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib
from _glbpose import Rig, min_pair_dist, knee_deg

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
rig = Rig(GLB)
m = rig.m
print('verts', rig.m.skin_verts(None, 0.0).shape, 'anims', list(m.anims))
for n in ['root','pelvis','spine','chest','neck','head','thigh.L','shin.L','foot.L','toe.01.L','thigh.R','shin.R','foot.R','toe.01.R']:
    if n in rig.joint_of:
        print('%-9s head %s dir %s' % (n, np.round(rig.head0(n),4), np.round(rig.dir0(n)/np.linalg.norm(rig.dir0(n)),4)))
print('thighL-shinL rest knee', round(knee_deg(rig, rig.W0, 'L'),3), 'R', round(knee_deg(rig, rig.W0, 'R'),3))

# ---- validation 1: identity pose via solve == rest
ch0, W0b = rig.solve({})
vA = rig.verts(ch0); vB = m.skin_verts(None, 0.0)
print('VALID1 identity max diff', float(np.abs(vA-vB).max()))

# ---- validation 2: reproduce Walk channels from world directions
walk = m.anims['Walk']
ts = walk[rig.joint_of['pelvis']]['translation'][0] if rig.joint_of['pelvis'] in walk else None
print('walk pelvis channel', rig.joint_of['pelvis'] in walk, 'frames', len(ts))
names = ['thigh.L','shin.L','foot.L','toe.01.L','toe.02.L','toe.03.L',
         'thigh.R','shin.R','foot.R','toe.01.R','toe.02.R','toe.03.R',
         'pelvis','spine','chest','neck','head','tail.001','tail.006',
         'shoulder.L','upper_arm.L','forearm.L','hand.L']
for label, t in [(16, 16/30.0), (24, 24/30.0)]:
    Ww = m.world(walk, t)
    dirs = {}; trans = {}
    for n in names:
        if n in rig.joint_of:
            j = rig.joint_of[n]
            dirs[n] = Ww[j][:3,:3] @ np.array([0,1.0,0])
    # pelvis translation delta relative to rest head
    jp = rig.joint_of['pelvis']
    trans['pelvis'] = Ww[jp][:3,3] - rig.W0[jp][:3,3]
    chS, WS = rig.solve(dirs, trans)
    vS = rig.verts(chS); vW = m.skin_verts(walk, t)
    print('VALID2 frame %d max diff %.5f  (nverts %d)' % (label, float(np.abs(vS-vW).max()), len(vS)))
    for side in 'LR':
        A,B = rig.sets(side)
        gw,_ = min_pair_dist(vW[A], vW[B]); gs,_ = min_pair_dist(vS[A], vS[B])
        print('   gap %s walk %.5f posed %.5f  knee %.1f' % (side, gw, gs, knee_deg(rig, Ww, side)))
