# -*- coding: utf-8 -*-
"""Numeric search for a knee<=24.7deg, pelvis 0.592-0.6098 walk pose family (bone level, no skinning)."""
import itertools, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _glbpose import Rig

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
UP = np.array([0., 1., 0.]); FWD = np.array([0., 0., 1.]); X = np.array([1., 0., 0.])
NF = 33
TOES = ['toe.01', 'toe.02', 'toe.03']
UPPER = ['spine','chest','neck','head','shoulder.L','upper_arm.L','forearm.L','hand.L',
         'shoulder.R','upper_arm.R','forearm.R','hand.R','tail.001','tail.002','tail.003',
         'tail.004','tail.005','tail.006']
KNEE_CAP = 24.7


def smooth(u): return u*u*(3-2*u)

def rot_axis(ax, deg):
    ax = np.asarray(ax, float); ax = ax/np.linalg.norm(ax)
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    K = np.array([[0,-ax[2],ax[1]],[ax[2],0,-ax[0]],[-ax[1],ax[0],0]])
    return np.eye(3) + s*K + (1-c)*(K@K)


class Walk:
    def __init__(self, rig, **p):
        self.rig = rig; self.p = p
        self.side = {}
        for s in 'LR':
            self.side[s] = dict(hip=rig.head0('thigh.'+s), ankle=rig.head0('foot.'+s),
                t=float(np.linalg.norm(rig.head0('shin.'+s)-rig.head0('thigh.'+s))),
                s=float(np.linalg.norm(rig.head0('foot.'+s)-rig.head0('shin.'+s))),
                fdir=rig.dir0('foot.'+s)/np.linalg.norm(rig.dir0('foot.'+s)))
        self.pelvis0 = rig.head0('pelvis')
        self.rel = {n: rig.head0(n)-self.pelvis0 for n in UPPER}
        for s in 'LR': self.rel['thigh.'+s] = self.side[s]['hip']-self.pelvis0

    def d25(self, s):
        d = self.side[s]; return float(np.sqrt(d['t']**2+d['s']**2+2*d['t']*d['s']*math.cos(math.radians(KNEE_CAP))))

    def pelvis(self, t):
        p = self.p
        yaw = p['YAW']*math.sin(2*math.pi*(t-0.05))
        roll = p['ROLL']*math.sin(2*math.pi*t)
        y = p['MID'] + p['AMP']*math.cos(4*math.pi*(t-0.31))
        x = self.pelvis0[0] + p['SWAY']*math.sin(2*math.pi*(t-0.25))
        return np.array([x, y, self.pelvis0[2]]), rot_axis(FWD, roll) @ rot_axis(UP, yaw)

    def traj(self, t, s):
        p = self.p
        ph = (t + (0.0 if s == 'L' else 0.5)) % 1.0
        if ph < p['DUTY']:
            u = ph/p['DUTY']
            return p['A'] - 2*p['A']*u, 0.0, ph, True
        u = (ph-p['DUTY'])/(1-p['DUTY'])
        return -p['A'] + 2*p['A']*smooth(u), p['LIFT']*math.sin(math.pi*u)**0.8, ph, False

    def frame(self, t):
        rig, p = self.rig, self.p
        ppos, prot = self.pelvis(t)
        heads = {'pelvis': ppos}; dirs = {'pelvis': UP}
        for n in UPPER: heads[n] = ppos + prot@self.rel[n]
        spin = math.sin(2*math.pi*t)
        dirs['spine'] = rot_axis(X, 1.6+0.8*spin) @ rig.dir0('spine')
        dirs['chest'] = rot_axis(X, 1.0-0.7*spin) @ rig.dir0('chest')
        dirs['neck'] = rot_axis(X, -1.2-0.6*spin) @ rig.dir0('neck')
        dirs['head'] = rot_axis(X, -0.8+0.5*spin) @ rig.dir0('head')
        for s in 'LR':
            lat = rig.head0('shoulder.'+s)-rig.head0('shoulder.'+('R' if s=='L' else 'L'))
            lat = lat/np.linalg.norm(lat)
            ph = 2*math.pi*(t+(0.0 if s=='L' else 0.5)); sw = p['ARM']*math.sin(ph)
            dirs['shoulder.'+s] = rot_axis(lat, 0.3*sw) @ rig.dir0('shoulder.'+s)
            dirs['upper_arm.'+s] = rot_axis(lat, sw) @ rig.dir0('upper_arm.'+s)
            dirs['forearm.'+s] = rot_axis(lat, sw-p['ELBOW']*(0.55+0.45*math.sin(ph-1.2))) @ rig.dir0('forearm.'+s)
            dirs['hand.'+s] = rot_axis(lat, sw-p['ELBOW']) @ rig.dir0('hand.'+s)
        for i, n in enumerate(['tail.001','tail.002','tail.003','tail.004','tail.005','tail.006']):
            amp = p['TAIL']*(0.35+0.65*i/5.0); phs = 2*math.pi*(t-0.10*i)
            dirs[n] = rot_axis(UP, amp*math.sin(phs)) @ rot_axis(X, 0.4*amp*math.cos(phs)) @ rig.dir0(n)
        info = {}
        for s in 'LR':
            d = self.side[s]
            hip = ppos + prot@self.rel['thigh.'+s]
            zoff, lift, ph, stance = self.traj(t, s)
            ax_rest = d['ankle']
            ankle = np.array([ax_rest[0], ax_rest[1]+lift, ax_rest[2]+zoff])
            heads['thigh.'+s] = hip
            knee, fdir, _ov = self._ik(s, hip, ankle)
            heads['shin.'+s] = knee; heads['foot.'+s] = ankle
            pnt = np.array(ankle, float); prev = 'foot.'+s
            for tb in TOES:
                n = tb+'.'+s; ln = float(np.linalg.norm(rig.head0(n)-rig.head0(prev)))
                pnt = pnt + fdir*ln; heads[n] = pnt.copy(); prev = n
            for n in ['foot.'+s]+[tb+'.'+s for tb in TOES]: dirs[n] = fdir
            dirs['thigh.'+s] = knee-hip; dirs['shin.'+s] = ankle-knee
            info[s] = dict(stance=stance, lift=lift, zoff=zoff, hip=hip, ankle=ankle)
        return heads, dirs, info

    def _ik(self, s, hip, ankle):
        d = self.side[s]; t1, t2 = d['t'], d['s']
        ax = ankle-hip; L = float(np.linalg.norm(ax)); Lmax = t1+t2
        over = L > Lmax
        if over: ax = ax/L*Lmax; L = Lmax
        u = ax/L
        a = (t1*t1-t2*t2+L*L)/(2*L); h = math.sqrt(max(t1*t1-a*a, 0.0))
        pole = FWD-np.dot(FWD, u)*u
        if np.linalg.norm(pole) < 1e-6: pole = X-np.dot(X, u)*u
        pole /= np.linalg.norm(pole)
        return hip+u*a+pole*h, d['fdir'], over

    def evaluate(self):
        rig = self.rig
        res = dict(knee={'L': [], 'R': []}, pel=[], lift={'L': [], 'R': []},
                   footz={'L': [], 'R': []}, over=0, anklegap={'L': [], 'R': []})
        for f in range(NF):
            t = f/float(NF-1)
            heads, dirs, info = self.frame(t)
            ch, W = rig.solve(dirs, heads=heads)
            res['pel'].append(float(W[rig.joint_of['pelvis']][1, 3]))
            for s in 'LR':
                tdir = W[rig.joint_of['thigh.'+s]][:3, :3]@UP
                sdir = W[rig.joint_of['shin.'+s]][:3, :3]@UP
                c = float(np.dot(tdir/np.linalg.norm(tdir), sdir/np.linalg.norm(sdir)))
                res['knee'][s].append(math.degrees(math.acos(max(-1., min(1., c)))))
                res['lift'][s].append(info[s]['lift'])
                res['footz'][s].append(float(W[rig.joint_of['foot.'+s]][2, 3]))
                # over-extension while planted would drag the foot off its target
                hip = info[s]['hip']; ank = info[s]['ankle']
                ex = float(np.linalg.norm(ank-hip)) - (self.side[s]['t']+self.side[s]['s'])
                res['anklegap'][s].append(ex if info[s]['stance'] else 0.0)
        res['over'] = max(max(res['anklegap']['L']), max(res['anklegap']['R']))
        return res


def score(res):
    k = max(max(res['knee']['L']), max(res['knee']['R']))
    pmin, pmax = min(res['pel']), max(res['pel'])
    clr = max(max(res['lift']['L']), max(res['lift']['R']))
    trav = {}
    for s in 'LR':
        fz = res['footz'][s]; st = []
        for i in range(len(fz)-1):
            ph = (i/float(NF-1) + (0.0 if s == 'L' else 0.5)) % 1.0
            if ph < 0.60: st.append(fz[i+1]-fz[i])
        trav[s] = -sum(st)
    return dict(knee=k, pel=(pmin, pmax), clr=clr, trav=trav, over=res['over'])


if __name__ == '__main__':
    rig = Rig(GLB)
    base = dict(DUTY=0.62, A=0.055, MID=0.6045, AMP=0.0045, ROLL=2.6, SWAY=0.006, YAW=2.0,
                LIFT=0.016, ARM=11.0, ELBOW=9.0, TAIL=2.6)
    for tag, ov in [('base', {}), ('flat', dict(AMP=0.0015, MID=0.6055)),
                    ('roll3.5', dict(ROLL=3.5, MID=0.6055, AMP=0.002))]:
        p = dict(base); p.update(ov)
        w = Walk(rig, **p)
        sc = score(w.evaluate())
        print('%-8s knee %.2f pel %.4f-%.4f clr %.4f trav L %.4f R %.4f over %.4f'
              % (tag, sc['knee'], sc['pel'][0], sc['pel'][1], sc['clr'], sc['trav']['L'], sc['trav']['R'], sc['over']))
