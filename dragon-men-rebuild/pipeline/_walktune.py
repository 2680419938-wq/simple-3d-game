import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _glbpose import Rig
import _walkgen32 as WG

rig = Rig(WG.GLB)

def cost(P):
    w = WG.Walk(rig, P); q = w.summary()
    c = 0.0
    c += 30*max(0.0, q['knee']-24.3)
    c += 200*q['over']
    c += 30*max(0.0, q['pel'][1]-0.6098)+30*max(0.0, 0.5930-q['pel'][0])
    c += 30*max(0.0, 0.0140-q['clr_min'])+30*max(0.0, q['clr_min']-0.0235)
    for s in 'LR':
        c += 30*max(0.0, abs(q['trav'][s])-0.125)+30*max(0.0, 0.090-abs(q['trav'][s]))
        c += 3.0*max(0.0, q['dev_'+s]-0.10)
    return c, q

rng = np.random.default_rng(5)
best = None
for it in range(1500):
    P = dict(DUTY=0.62, YAW=2.0, SWAY=0.006, KNEE_CLAMP=24.0,
             A=float(rng.uniform(0.046, 0.062)), MID=float(rng.uniform(0.6020, 0.6075)),
             AMP=float(rng.uniform(0.0005, 0.0045)), ROLL=float(rng.uniform(0.0, 2.5)),
             SPLAY=float(rng.uniform(0.0, 0.085)), PH=float(rng.uniform(0.05, 0.55)),
             UPOW=float(rng.uniform(0.8, 2.0)), LIFT=float(rng.uniform(0.014, 0.030)))
    c, q = cost(P)
    if best is None or c < best[0]: best = (c, q, P)
c, q, P = best
print('coarse %.4f' % c)
for step in (0.004, 0.002, 0.001, 0.0004, 0.0002, 0.0001):
    imp = True
    while imp:
        imp = False
        for k, sc in (('A', 1.0), ('MID', 0.25), ('AMP', 0.3), ('ROLL', 0.5), ('SPLAY', 1.0),
                      ('PH', 0.05), ('UPOW', 0.5), ('LIFT', 1.0), ('SWAY', 1.0), ('YAW', 1.0)):
            for sg in (1, -1):
                Q = dict(P); Q[k] = P[k]+sg*step*sc
                cq, qq = cost(Q)
                if cq < c-1e-9: P, c, q = Q, cq, qq; imp = True
print('refined %.5f' % c)
print({k: round(float(v), 5) for k, v in P.items()})
print('knee %.2f pel %.4f-%.4f clrL %.4f clrR %.4f trav L %.4f R %.4f devL %.2f%% devR %.2f%%'
      % (q['knee'], q['pel'][0], q['pel'][1], q['clr']['L'], q['clr']['R'],
         q['trav']['L'], q['trav']['R'], 100*q['dev_L'], 100*q['dev_R']))
json.dump({k: float(v) for k, v in P.items()}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_walkparams.json'), 'w'), indent=1)
