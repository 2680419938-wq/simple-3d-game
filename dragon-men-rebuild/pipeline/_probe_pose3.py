# -*- coding: utf-8 -*-
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib
from _glbpose import Rig, min_pair_dist, knee_deg

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
rig = Rig(GLB); m = rig.m; walk = m.anims['Walk']

def pose_from(W, side):
    chain = ['thigh.'+side,'shin.'+side,'foot.'+side,'toe.01.'+side,'toe.02.'+side,'toe.03.'+side]
    heads = {n: W[rig.joint_of[n]][:3,3].copy() for n in chain}
    dirs = {'thigh.'+side: heads['shin.'+side]-heads['thigh.'+side],
            'shin.'+side: heads['foot.'+side]-heads['shin.'+side]}
    fd = W[rig.joint_of['toe.01.'+side]][:3,:3] @ np.array([0,1.,0])
    for n in ['foot.'+side,'toe.01.'+side,'toe.02.'+side,'toe.03.'+side]: dirs[n] = fd
    return rig.solve(dirs, heads=heads)

for f in (8, 16, 24, 30):
    t = f/30.0
    Ww = m.world(walk, t)
    vW = m.skin_verts(walk, t)
    for side in 'LR':
        ch, WS = pose_from(Ww, side)
        vS = rig.verts(ch)
        A,B = rig.sets(side)
        sel = np.concatenate([A,B])
        d = np.linalg.norm(vS[sel]-vW[sel],axis=1)
        print('f%-3d %s legset maxdiff %.6f  gap walk %.5f posed %.5f' % (f, side, float(d.max()),
              min_pair_dist(vW[A],vW[B])[0], min_pair_dist(vS[A],vS[B])[0]))
