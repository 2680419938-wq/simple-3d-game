# -*- coding: utf-8 -*-
import sys, numpy as np
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\pipeline')
from glblib import Model, acc
GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
m = Model(GLB)
dom = m.dominant_joint_names()
print('verts', len(dom), 'tris', m.tris)
def sets(side):
    T = np.nonzero(dom == 'thigh.'+side)[0]
    S = np.nonzero((dom == 'shin.'+side) | (dom == 'foot.'+side) | (np.char.startswith(dom.astype(str),'toe.') & np.char.endswith(dom.astype(str),'.'+side)))[0]
    return T, S
def mind(A,B,chunk=256):
    best=1e9; bi=bj=-1
    for i in range(0,len(A),chunk):
        d=np.linalg.norm(A[i:i+chunk,None,:]-B[None,:,:],axis=2)
        k=np.unravel_index(int(np.argmin(d)), d.shape)
        if d[k]<best: best=float(d[k]); bi=i+k[0]; bj=k[1]
    return best, bi, bj
for side in 'LR':
    T,S = sets(side)
    print(side, 'thigh verts', len(T), 'shin/foot/toe verts', len(S))
    Vr = m.skin_verts(None, 0.0)
    g,ti,tj = mind(Vr[T], Vr[S])
    print('  REST gap %.5f  thigh vert %d %s  shin vert %d %s' % (g, T[ti], np.round(Vr[T[ti]],4), S[tj], np.round(Vr[S[tj]],4)))
    for anim in ('Idle_Lively','Walk'):
        ch = m.anims[anim]
        times = sorted(set(float(x) for v in ch.values() for tup in v.values() for x in tup[0]))
        times = np.array(times)
        worst=(0,None); best=(9,None)
        for f,t in enumerate(times[:33] if anim=='Walk' else times[:121:10]):
            V = m.skin_verts(ch, float(t))
            g,ti,tj = mind(V[T],V[S])
            if g>worst[0]: worst=(g,(f+1,float(t),int(T[ti]),int(S[tj])))
            if g<best[0]: best=(g,(f+1,float(t),int(T[ti]),int(S[tj])))
        print('  %s: min %.5f %s | max %.5f %s' % (anim, best[0], best[1], worst[0], worst[1]))
