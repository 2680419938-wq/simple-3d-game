# -*- coding: utf-8 -*-
"""What is the L thigh shell, the L greave, and where is the 6 cm gap?"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib
from _glbpose import Rig, min_pair_dist

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
rig = Rig(GLB); m = rig.m; g = m.g
V0 = m.skin_verts(None, 0.0)
dom = rig.dom
print('dominant counts:', {n:int((dom==n).sum()) for n in sorted(set(dom)) if 'thigh' in n or 'shin' in n or 'foot' in n or 'toe' in n})

for s in 'LR':
    A = np.where(dom=='thigh.'+s)[0]; B = np.where(np.isin(dom,['shin.'+s,'foot.'+s,'toe.01.'+s,'toe.02.'+s,'toe.03.'+s]))[0]
    print('=== side', s, 'thigh', len(A), 'shin+foot', len(B))
    print('  thigh bbox', np.round(V0[A].min(0),3), np.round(V0[A].max(0),3))
    print('  shin  bbox', np.round(V0[B].min(0),3), np.round(V0[B].max(0),3))
    gap,(i,j) = min_pair_dist(V0[A],V0[B])
    print('  gap %.5f pair thigh#%d %s  shin#%d %s  d=%s' % (gap, A[i], np.round(V0[A[i]],4), B[j], np.round(V0[B[j]],4), np.round(V0[B[j]]-V0[A[i]],4)))
    # which of the shin+foot verts are above mid-shin (greave top)?
    knee = rig.head0('shin.'+s); ank = rig.head0('foot.'+s)
    above = B[V0[B][:,1] > (knee[1]-ank[1])*0.0 + ank[1] + (knee[1]-ank[1])*0.5]
    print('  shin+foot verts above mid-shin: %d  dominant mix %s' % (len(above), {n:int((dom[above]==n).sum()) for n in set(dom[above])}))
    if len(above):
        print('  top-most of them y=%.4f' % V0[above][:,1].max())
        top = above[np.argsort(-V0[above][:,1])[:5]]
        for k in top: print('     #%d %s dom=%s' % (k, np.round(V0[k],4), dom[k]))
