import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _glbpose import Rig
import _walkgen32 as WG
rig = Rig(WG.GLB)
w = WG.Walk(rig, dict(SPLAY=0.03))
r = w.probe()
for s in 'LR':
    fz = r['footz'][s]
    print('side', s, 'stance flags', ''.join('S' if x else '.' for x in r['stance'][s]))
    steps = []
    for i in range(len(fz)-1):
        if r['stance'][s][i] and r['stance'][s][i+1]:
            steps.append(round(fz[i+1]-fz[i], 6))
    print('  steps', steps)
