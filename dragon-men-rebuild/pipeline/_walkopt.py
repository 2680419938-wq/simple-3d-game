# -*- coding: utf-8 -*-
"""Analytic (no skinning) search for a walk that keeps knee <= 24.7 deg on both legs while the
pelvis stays in 0.592..0.6098 and the swing foot clears >= 0.013 m.

Each stance leg planted at its rest ankle height; swing foot lifted along a clamped bump;
pelvic roll (sin^2 bump on the swing side) buys extra reach budget for the swing foot.
"""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _glbpose import Rig

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
UP = np.array([0., 1., 0.]); FWD = np.array([0., 0., 1.]); X = np.array([1., 0., 0.])
NF, DUTY = 33, 0.62
KNEE_CAP = 24.7


def smooth(u): return u*u*(3-2*u)
def rot_axis(ax, deg):
    ax = np.asarray(ax, float); ax = ax/np.linalg.norm(ax)
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    K = np.array([[0,-ax[2],ax[1]],[ax[2],0,-ax[0]],[-ax[1],ax[0],0]])
    return np.eye(3)+s*K+(1-c)*(K@K)


class Geo:
    def __init__(self, rig):
        self.rig = rig
        self.side = {}
        for s in 'LR':
            self.side[s] = dict(
                hip=rig.head0('thigh.'+s), ank=rig.head0('foot.'+s),
                t=float(np.linalg.norm(rig.head0('shin.'+s)-rig.head0('thigh.'+s))),
                sh=float(np.linalg.norm(rig.head0('foot.'+s)-rig.head0('shin.'+s))))
            d = self.side[s]
            self.side[s]['D0'] = d['t']+d['sh']
            self.side[s]['D25'] = float(np.sqrt(d['t']**2+d['sh']**2+2*d['t']*d['sh']*math.cos(math.radians(KNEE_CAP))))
        self.p0 = rig.head0('pelvis')
        self.relhip = {s: self.side[s]['hip']-self.p0 for s in 'LR'}

    def eval(self, P):
        """P: dict(A, MID, AMP, ROLL, LIFT, PH) -> per-frame diagnostics."""
        out = dict(knee={'L': [], 'R': []}, pel=[], lift={'L': [], 'R': []},
                   over={'L': [], 'R': []}, hipy={'L': [], 'R': []})
        for f in range(NF):
            t = f/float(NF-1)
            # --- swing bump (sin^2) per side, drives the pelvic roll
            bumps = {}
            for s in 'LR':
                ph = (t+(0.0 if s == 'L' else 0.5)) % 1.0
                bumps[s] = 0.0 if ph < DUTY else math.sin(math.pi*(ph-DUTY)/(1-DUTY))**2
            roll = P['ROLL']*(bumps['L']-bumps['R'])          # + raises the L hip
            yaw = P['YAW']*math.sin(2*math.pi*(t-0.05))
            prot = rot_axis(FWD, roll) @ rot_axis(UP, yaw)
            py = P['MID']+P['AMP']*math.cos(4*math.pi*(t-P['PH']))
            px = self.p0[0]+P['SWAY']*math.sin(2*math.pi*(t-0.25))
            ppos = np.array([px, py, self.p0[2]])
            out['pel'].append(py)
            for s in 'LR':
                d = self.side[s]
                hip = ppos+prot@self.relhip[s]
                ph = (t+(0.0 if s == 'L' else 0.5)) % 1.0
                if ph < DUTY:
                    u = ph/DUTY; zoff = P['A']-2*P['A']*u; lift = 0.0; stance = True
                else:
                    u = (ph-DUTY)/(1-DUTY); zoff = -P['A']+2*P['A']*smooth(u)
                    lift = P['LIFT']*math.sin(math.pi*u)**0.8; stance = False
                ax = d['ank'][0]; az = d['ank'][2]+zoff
                ay = d['ank'][1]+lift
                h = math.hypot(ax-hip[0], az-hip[2])
                vert = hip[1]-ay
                if vert < 0: vert = 0.0
                D = math.hypot(vert, h)
                budget = (hip[1]-d['ank'][1])-math.sqrt(max(d['D25']**2-h*h, 0.0))
                if not stance and lift > max(budget, 0.0):
                    lift = max(budget, 0.0); ay = d['ank'][1]+lift; vert = hip[1]-ay
                    D = math.hypot(max(vert, 0.0), h)
                c = (d['t']**2+d['sh']**2-D*D)/(2*d['t']*d['sh'])
                out['knee'][s].append(math.degrees(math.acos(max(-1., min(1., c)))))
                out['lift'][s].append(lift)
                out['over'][s].append(max(0.0, D-d['D0']))
                out['hipy'][s].append(hip[1])
        return out


def cost(res, P, verbose=False):
    kmax = max(max(res['knee']['L']), max(res['knee']['R']))
    over = max(max(res['over']['L']), max(res['over']['R']))
    pmin, pmax = min(res['pel']), max(res['pel'])
    clr = max(max(res['lift']['L']), max(res['lift']['R']))
    c = 0.0
    c += 10.0*max(0.0, kmax-KNEE_CAP)
    c += 100.0*over
    c += 10.0*max(0.0, pmax-0.6098)+10.0*max(0.0, 0.592-pmin)
    c += 10.0*max(0.0, 0.0135-clr)+10.0*max(0.0, clr-0.023)
    if verbose:
        print('knee %.2f over %.4f pel %.4f..%.4f clr %.4f' % (kmax, over, pmin, pmax, clr))
    return c, dict(knee=kmax, over=over, pel=(pmin, pmax), clr=clr)


if __name__ == '__main__':
    rig = Rig(GLB); g = Geo(rig)
    rng = np.random.default_rng(7)
    best = None
    base = dict(A=0.052, MID=0.6050, AMP=0.0030, ROLL=2.4, LIFT=0.020, PH=0.31, YAW=2.0, SWAY=0.006)
    for it in range(4000):
        P = dict(base)
        if it:
            P.update(A=float(rng.uniform(0.045, 0.062)), MID=float(rng.uniform(0.5985, 0.6075)),
                     AMP=float(rng.uniform(0.0005, 0.0060)), ROLL=float(rng.uniform(0.0, 3.2)),
                     LIFT=float(rng.uniform(0.012, 0.030)), PH=float(rng.uniform(0.05, 0.55)))
        c, m = cost(g.eval(P), P)
        if best is None or c < best[0]: best = (c, m, P)
    c, m, P = best
    print('BEST cost %.5f' % c); print(json.dumps(P, indent=1) if False else P)
    cost(g.eval(P), P, verbose=True)
    res = g.eval(P)
    for f in range(NF):
        print('f%02d pel %.4f kneeL %5.2f kneeR %5.2f liftL %.4f liftR %.4f overL %.4f overR %.4f'
              % (f+1, res['pel'][f], res['knee']['L'][f], res['knee']['R'][f], res['lift']['L'][f],
                 res['lift']['R'][f], res['over']['L'][f], res['over']['R'][f]))
