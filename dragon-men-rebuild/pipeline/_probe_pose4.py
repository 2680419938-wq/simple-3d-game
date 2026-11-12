# -*- coding: utf-8 -*-
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib
from _glbpose import Rig

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
rig = Rig(GLB); m = rig.m; walk = m.anims['Walk']; g=m.g
t = 16/30.0
Ww = m.world(walk, t)
side='R'
chain = ['thigh.'+side,'shin.'+side,'foot.'+side,'toe.01.'+side,'toe.02.'+side,'toe.03.'+side]
heads = {n: Ww[rig.joint_of[n]][:3,3].copy() for n in chain}
dirs = {'thigh.'+side: heads['shin.'+side]-heads['thigh.'+side],'shin.'+side: heads['foot.'+side]-heads['shin.'+side]}
fd = Ww[rig.joint_of['toe.01.'+side]][:3,:3] @ np.array([0,1.,0])
for n in ['foot.'+side,'toe.01.'+side,'toe.02.'+side,'toe.03.'+side]: dirs[n]=fd
ch, WS = rig.solve(dirs, heads=heads)
vS = rig.verts(ch); vW = m.skin_verts(walk, t)
A,B = rig.sets(side); sel=np.concatenate([A,B])
d = np.linalg.norm(vS[sel]-vW[sel],axis=1)
order=np.argsort(-d)[:6]
# gather weight info
mesh=g['meshes'][m.nodes[m.meshnode]['mesh']]
J=[];Wt=[]
off=0
for pr in mesh['primitives']:
    J.append(glblib.acc(g,m.bin,pr['attributes']['JOINTS_0']).astype(int)); Wt.append(glblib.acc(g,m.bin,pr['attributes']['WEIGHTS_0']))
    off+=len(J[-1])
J=np.vstack(J); Wt=np.vstack(Wt)
for k in order:
    vi = sel[k]
    ws = [(rig.m.jnames[J[vi,c]], round(float(Wt[vi,c]),3)) for c in range(4) if Wt[vi,c]>0.001]
    print('vert#%d diff %.4f dom=%s weights=%s' % (vi, d[k], rig.dom[vi], ws))
