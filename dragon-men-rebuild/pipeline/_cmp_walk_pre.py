# -*- coding: utf-8 -*-
"""Pre-check on game-34: does Walk loop exactly (f1==f33) and what is the floor clearance
excluding the armor-plate vertices that the walk32 build will delete?"""
import sys, numpy as np
sys.path.insert(0, r"D:\ai\建模\dragon-men-rebuild\pipeline")
from glblib import Model, acc
m = Model(r"D:\ai\建模\dragon-men-game-34\DragonMan_Game.glb")
ch = m.anims['Walk']
t0 = min(float(v['rotation'][0][0]) for v in ch.values() if 'rotation' in v)
t1 = max(float(v['rotation'][0][-1]) for v in ch.values() if 'rotation' in v)
nkeys = max(len(v['rotation'][0]) for v in ch.values() if 'rotation' in v)
print("Walk t=[%.6f..%.6f] dur=%.6f keys=%d" % (t0, t1, t1 - t0, nkeys))
W0 = m.world(ch, t0); W1 = m.world(ch, t1)
d = max(float(np.abs(W0[i] - W1[i]).max()) for i in range(m.N))
print("first-vs-last world-matrix max diff = %.3e" % d)

dom = m.dominant_joint_names()
keep = ~np.char.startswith(dom.astype(str), 'armor_knee')
print("verts total %d, non-armor %d" % (len(dom), keep.sum()))
for f in range(33):
    t = t0 + (t1 - t0) * f / 32.0
    V = m.skin_verts(ch, t)
    y = V[:, 1]
    print("f%02d t=%.4f  all_min=%+.5f  nonarmor_min=%+.5f" % (f + 1, t, y.min(), y[keep].min()))
