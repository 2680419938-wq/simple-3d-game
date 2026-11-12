# -*- coding: utf-8 -*-
import sys, numpy as np
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\pipeline')
import glblib as G
m = G.Model(r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb')
a = m.anims['Walk']
worst = []
for ni, paths in a.items():
    for path, (times, vals, interp) in paths.items():
        d = np.abs(np.asarray(vals[0], dtype=np.float64) - np.asarray(vals[-1], dtype=np.float64)).max()
        if d > 0:
            worst.append((float(d), ni, path, m.N[ni]))
worst.sort(reverse=True)
print('channels whose first/last key differ:', len(worst))
for d, ni, path, nm in worst[:8]:
    print('  %-10s %-10s delta %.3e' % (nm, path, d))
W0 = m.world(a, 0.0); W1 = m.world(a, 32 / 30.0)
for nm in ['pelvis', 'thigh.L', 'shin.L', 'foot.L', 'chest', 'toe.03.R']:
    ni = m.N.index(nm)
    print('%-10s world delta %.3e' % (nm, np.abs(np.asarray(W0[ni]) - np.asarray(W1[ni])).max()))
