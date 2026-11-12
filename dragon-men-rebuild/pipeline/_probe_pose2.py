# -*- coding: utf-8 -*-
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib
from _glbpose import Rig

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
rig = Rig(GLB); m = rig.m
walk = m.anims['Walk']
t = 16/30.0
Ww = m.world(walk, t)

def ang(u,v):
    u=u/np.linalg.norm(u); v=v/np.linalg.norm(v)
    return float(np.degrees(np.arccos(np.clip(np.dot(u,v),-1,1))))

# all joints, dirs only (no trans) -- which joints move at all?
changed=[]
for k,j in enumerate(rig.m.joints):
    n = rig.m.jnames[k]
    d0 = rig.W0[j][:3,:3] @ np.array([0,1.,0]); d1 = Ww[j][:3,:3] @ np.array([0,1.,0])
    h0 = rig.W0[j][:3,3]; h1 = Ww[j][:3,3]
    if ang(d0,d1) > 0.01 or np.linalg.norm(h1-h0) > 1e-5:
        changed.append((n, round(ang(d0,d1),2), round(float(np.linalg.norm(h1-h0)),4)))
print('changed joints:', changed)

# pose ONLY thigh.L / shin.L / foot.L from Ww; then compare their world dirs+heads
dirs = {n: Ww[rig.joint_of[n]][:3,:3] @ np.array([0,1.,0]) for n in ['thigh.L','shin.L','foot.L']}
chS, WS = rig.solve(dirs)
for n in ['thigh.L','shin.L','foot.L']:
    j = rig.joint_of[n]
    print('%-8s direrr %.4f  headerr %.5f' % (n, ang(WS[j][:3,:3]@np.array([0,1.,0]), Ww[j][:3,:3]@np.array([0,1.,0])),
          float(np.linalg.norm(WS[j][:3,3]-Ww[j][:3,3]))))
    # local rest vs animated local
    p = m.par[j]
    L0 = rig.L0[j]; Lw = np.linalg.inv(Ww[p]) @ Ww[j]
    print('   local scale rest', np.round(np.linalg.norm(rig.W0[j][:3,:3],axis=0),4), 'anim',
          np.round(np.linalg.norm(Lw[:3,:3],axis=0),4), 'restL', np.round(np.linalg.norm(L0[:3,:3],axis=0),4))
# what channels does Walk animate?
print('anim channels nodes:', [(rig.m.jnames[[i for i,jj in enumerate(rig.m.joints) if jj==nd][0]] if nd in rig.m.joints else nd,
       sorted(d.keys())) for nd,d in list(walk.items())[:40]])
