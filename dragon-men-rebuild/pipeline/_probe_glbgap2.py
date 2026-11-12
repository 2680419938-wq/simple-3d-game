# -*- coding: utf-8 -*-
import sys, numpy as np
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\pipeline')
from glblib import Model, acc
m = Model(r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb')
dom = m.dominant_joint_names()
T = np.nonzero(dom=='thigh.L')[0]
S = np.nonzero((dom=='shin.L')|(dom=='foot.L')|(np.char.startswith(dom.astype(str),'toe.')&np.char.endswith(dom.astype(str),'.L')))[0]
print('T', len(T), 'S', len(S))
def pairs(A,B,k=6):
    d=np.linalg.norm(A[:,None,:]-B[None,:,:],axis=2)
    flat=np.argsort(d,axis=None)[:k]
    out=[]
    for idx in flat:
        i,j=np.unravel_index(idx,d.shape)
        out.append((float(d[i,j]),int(i),int(j)))
    return out
for tag, ch, t in (('REST', None, 0.0), ('IDLE f3', m.anims['Idle_Lively'], 0.6666666865348816), ('WALK f11', m.anims['Walk'], 0.3333)):
    if ch is None:
        V = m.skin_verts(None, 0.0)
    else:
        V = m.skin_verts(ch, t)
    print('====', tag)
    for d,i,j in pairs(V[T],V[S],6):
        print('  %.5f  T#%d %s dom=%s   S#%d %s dom=%s' % (d, T[i], np.round(V[T[i]],4), dom[T[i]], S[j], np.round(V[S[j]],4), dom[S[j]]))
# where is the L thigh shell / shin shell in rest? z ranges
Vr = m.skin_verts(None,0.0)
print('L thigh shell bbox', np.round([Vr[T].min(0),Vr[T].max(0)],3).tolist())
print('L shin/foot  bbox', np.round([Vr[S].min(0),Vr[S].max(0)],3).tolist())
# shin.L dominant verts only
SL = np.nonzero(dom=='shin.L')[0]; FL=np.nonzero(dom=='foot.L')[0]
print('L shin-only verts', len(SL), np.round([Vr[SL].min(0),Vr[SL].max(0)],3).tolist() if len(SL) else '-')
print('L foot-only verts', len(FL), np.round([Vr[FL].min(0),Vr[FL].max(0)],3).tolist())
