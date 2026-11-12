import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _walkopt as WO
from _glbpose import Rig

GLB = WO.GLB
rig = Rig(GLB); g = WO.Geo(rig)
NF = WO.NF

# fixed knee formula: interior triangle angle -> bend = 180 - interior
def knee_of(s, D):
    d = g.side[s]
    c = (d['t']**2+d['sh']**2-D*D)/(2*d['t']*d['sh'])
    return 180.0-math.degrees(math.acos(max(-1., min(1., c))))

def ev(P):
    """same as Geo.eval but with the corrected knee angle"""
    res = dict(knee={'L': [], 'R': []}, pel=[], lift={'L': [], 'R': []}, over={'L': [], 'R': []})
    for f in range(NF):
        t = f/float(NF-1)
        bumps = {}
        for s in 'LR':
            ph = (t+(0.0 if s == 'L' else 0.5)) % 1.0
            bumps[s] = 0.0 if ph < WO.DUTY else math.sin(math.pi*(ph-WO.DUTY)/(1-WO.DUTY))**2
        roll = P['ROLL']*(bumps['L']-bumps['R'])
        yaw = P['YAW']*math.sin(2*math.pi*(t-0.05))
        prot = WO.rot_axis(WO.FWD, roll) @ WO.rot_axis(WO.UP, yaw)
        py = P['MID']+P['AMP']*math.cos(4*math.pi*(t-P['PH']))
        px = g.p0[0]+P['SWAY']*math.sin(2*math.pi*(t-0.25))
        ppos = np.array([px, py, g.p0[2]])
        res['pel'].append(py)
        for s in 'LR':
            d = g.side[s]; hip = ppos+prot@g.relhip[s]
            ph = (t+(0.0 if s == 'L' else 0.5)) % 1.0
            if ph < WO.DUTY:
                u = ph/WO.DUTY; zoff = P['A']-2*P['A']*u; lift = 0.0; stance = True
            else:
                u = (ph-WO.DUTY)/(1-WO.DUTY); zoff = -P['A']+2*P['A']*WO.smooth(u)
                lift = P['LIFT']*math.sin(math.pi*u)**0.8; stance = False
            ay = d['ank'][1]+lift
            h = math.hypot(d['ank'][0]-hip[0], d['ank'][2]+zoff-hip[2])
            budget = (hip[1]-d['ank'][1])-math.sqrt(max(d['D25']**2-h*h, 0.0))
            if not stance and lift > max(budget, 0.0):
                lift = max(budget, 0.0); ay = d['ank'][1]+lift
            D = math.hypot(max(hip[1]-ay, 1e-9), h)
            res['knee'][s].append(knee_of(s, D))
            res['lift'][s].append(lift); res['over'][s].append(max(0.0, D-d['D0']))
    return res

def cost(res):
    kmax = max(max(res['knee']['L']), max(res['knee']['R']))
    over = max(max(res['over']['L']), max(res['over']['R']))
    pmin, pmax = min(res['pel']), max(res['pel'])
    clr = max(max(res['lift']['L']), max(res['lift']['R']))
    c = 10*max(0., kmax-23.5)+100*over+10*max(0., pmax-0.6098)+10*max(0., 0.592-pmin)
    c += 10*max(0., 0.0140-clr)+10*max(0., clr-0.023)
    return c, dict(knee=kmax, over=over, pel=(pmin, pmax), clr=clr)

rng = np.random.default_rng(11)
best = None
for it in range(6000):
    P = dict(YAW=2.0, SWAY=0.006,
             A=float(rng.uniform(0.045, 0.063)), MID=float(rng.uniform(0.5975, 0.6085)),
             AMP=float(rng.uniform(0.0005, 0.0060)), ROLL=float(rng.uniform(0.0, 3.4)),
             LIFT=float(rng.uniform(0.014, 0.030)), PH=float(rng.uniform(0.05, 0.55)))
    c, m = cost(ev(P))
    if best is None or c < best[0]: best = (c, m, P)
c, m, P = best
print('coarse', round(c, 5), m)
# local refinement
for step in (0.004, 0.002, 0.001, 0.0005, 0.0002):
    improved = True
    while improved:
        improved = False
        for k, sc in (('A', 1.0), ('MID', 0.25), ('AMP', 0.3), ('ROLL', 0.4), ('LIFT', 1.0), ('PH', 0.05)):
            for sgn in (1, -1):
                Q = dict(P); Q[k] = P[k]+sgn*step*sc
                cq, mq = cost(ev(Q))
                if cq < c-1e-9: P, c, m = Q, cq, mq; improved = True
print('refined', round(c, 6), m)
print({k: round(v, 5) for k, v in P.items()})
res = ev(P)
for f in range(NF):
    print('f%02d pel %.4f kneeL %5.2f kneeR %5.2f liftL %.4f liftR %.4f overL %.4f overR %.4f'
          % (f+1, res['pel'][f], res['knee']['L'][f], res['knee']['R'][f], res['lift']['L'][f],
             res['lift']['R'][f], res['over']['L'][f], res['over']['R'][f]))
import json
json.dump({k: float(v) for k, v in P.items()}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_walkparams.json'), 'w'), indent=1)
