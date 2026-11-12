# -*- coding: utf-8 -*-
"""New 33-frame Walk for the 32-bone dragon-man rig.

Design constraints (parent brief, m00001):
  * knee bend peak <= 25 deg, pelvis height inside 0.590..0.610 m
  * stance foot slides back 0.08..0.13 m, uniform; swing foot clears 0.012..0.025 m
  * implicit ground speed 0.15..0.24 m/s -> 2*A*2 per cycle / 1.0667 s
Authoring space: the shipped GLB ("glTF world": +Y up, +Z forward, X lateral, L = +X).
Bone local TRS are frame invariant, so matrix_basis built here is fed straight back to Blender.

  python _walkgen32.py                 # analytic probe (knee/pelvis/clearance/travel)
  python _walkgen32.py --report        # + skinned GLB metrics (seam distance, min z)
  python _walkgen32.py --emit <json>   # 33 frames x 32 bones matrix_basis for the build
"""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib
from _glbpose import Rig, min_pair_dist, knee_deg

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
UP = np.array([0., 1., 0.]); FWD = np.array([0., 0., 1.]); X = np.array([1., 0., 0.])
NF = 33
TOES = ['toe.01', 'toe.02', 'toe.03']
UPPER = ['spine', 'chest', 'neck', 'head',
         'shoulder.L', 'upper_arm.L', 'forearm.L', 'hand.L',
         'shoulder.R', 'upper_arm.R', 'forearm.R', 'hand.R',
         'tail.001', 'tail.002', 'tail.003', 'tail.004', 'tail.005', 'tail.006']
P = dict(DUTY=0.62, A=0.0500, MID=0.6050, AMP=0.0040, PH=0.27, ROLL=2.0, YAW=2.0, SWAY=0.006,
         LIFT=0.030, UPOW=0.8, SPLAY=0.0, FOOTP=8.0, ARM=11.0, ELBOW=9.0, TAIL=2.6,
         KNEE_CLAMP=24.0)


def smooth(u): return u*u*(3-2*u)
def rot_axis(ax, deg):
    ax = np.asarray(ax, float); ax = ax/np.linalg.norm(ax)
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3)+s*K+(1-c)*(K@K)


class Walk:
    def __init__(self, rig, p=None):
        self.rig = rig; self.p = dict(P); self.p.update(p or {})
        self.side = {}
        for s in 'LR':
            self.side[s] = dict(
                hip=rig.head0('thigh.'+s), ank=rig.head0('foot.'+s),
                t=float(np.linalg.norm(rig.head0('shin.'+s)-rig.head0('thigh.'+s))),
                sh=float(np.linalg.norm(rig.head0('foot.'+s)-rig.head0('shin.'+s))),
                fdir=rig.dir0('foot.'+s)/np.linalg.norm(rig.dir0('foot.'+s)))
            d = self.side[s]
            d['D0'] = d['t']+d['sh']
            d['D25'] = float(np.sqrt(d['t']**2+d['sh']**2+2*d['t']*d['sh']*math.cos(math.radians(self.p['KNEE_CLAMP']))))
        self.p0 = rig.head0('pelvis')
        self.rel = {n: rig.head0(n)-self.p0 for n in UPPER}
        for s in 'LR': self.rel['thigh.'+s] = self.side[s]['hip']-self.p0

    # ---------- pelvis ----------
    def bumps(self, t):
        b = {}
        for s in 'LR':
            ph = (t+(0.0 if s == 'L' else 0.5)) % 1.0
            b[s] = 0.0 if ph < self.p['DUTY'] else math.sin(math.pi*(ph-self.p['DUTY'])/(1-self.p['DUTY']))**2
        return b

    def pelvis(self, t):
        p = self.p; b = self.bumps(t)
        roll = p['ROLL']*(b['L']-b['R'])                       # + raises the L hip
        yaw = p['YAW']*math.sin(2*math.pi*(t-0.05))
        prot = rot_axis(FWD, roll) @ rot_axis(UP, yaw)
        y = p['MID']+p['AMP']*math.cos(4*math.pi*(t-p['PH']))
        x = self.p0[0]+p['SWAY']*math.sin(2*math.pi*(t-0.25))
        return np.array([x, y, self.p0[2]]), prot, roll

    # ---------- foot trajectory ----------
    def traj(self, t, s):
        p = self.p; L = 1.0 if s == 'L' else -1.0
        ph = (t+(0.0 if s == 'L' else 0.5)) % 1.0
        if ph < p['DUTY']:
            u = ph/p['DUTY']
            return p['A']-2*p['A']*u, 0.0, 0.0, ph, True
        u = (ph-p['DUTY'])/(1-p['DUTY'])
        lift = p['LIFT']*math.sin(math.pi*u)**p['UPOW']
        splay = p['SPLAY']*math.sin(math.pi*u)*(1.0 if s == 'L' else 1.0)*L
        return -p['A']+2*p['A']*smooth(u), lift, splay, ph, False

    # ---------- one frame ----------
    def frame(self, t, lift_scale=1.0):
        rig, p = self.rig, self.p
        ppos, prot, roll = self.pelvis(t)
        heads = {'pelvis': ppos}; dirs = {'pelvis': UP}
        for n in UPPER: heads[n] = ppos+prot@self.rel[n]
        spin = math.sin(2*math.pi*t)
        dirs['spine'] = rot_axis(X, 1.6+0.8*spin) @ rig.dir0('spine')
        dirs['chest'] = rot_axis(X, 1.0-0.7*spin) @ rig.dir0('chest')
        dirs['neck'] = rot_axis(X, -1.2-0.6*spin) @ rig.dir0('neck')
        dirs['head'] = rot_axis(X, -0.8+0.5*spin) @ rig.dir0('head')
        for s in 'LR':
            lat = rig.head0('shoulder.'+s)-rig.head0('shoulder.'+('R' if s == 'L' else 'L'))
            lat = lat/np.linalg.norm(lat)
            ph = 2*math.pi*(t+(0.0 if s == 'L' else 0.5)); sw = p['ARM']*math.sin(ph)
            dirs['shoulder.'+s] = rot_axis(lat, 0.3*sw) @ rig.dir0('shoulder.'+s)
            dirs['upper_arm.'+s] = rot_axis(lat, sw) @ rig.dir0('upper_arm.'+s)
            dirs['forearm.'+s] = rot_axis(lat, sw-p['ELBOW']*(0.55+0.45*math.sin(ph-1.2))) @ rig.dir0('forearm.'+s)
            dirs['hand.'+s] = rot_axis(lat, sw-p['ELBOW']) @ rig.dir0('hand.'+s)
        for i, n in enumerate(['tail.001', 'tail.002', 'tail.003', 'tail.004', 'tail.005', 'tail.006']):
            amp = p['TAIL']*(0.35+0.65*i/5.0); phs = 2*math.pi*(t-0.10*i)
            dirs[n] = rot_axis(UP, amp*math.sin(phs)) @ rot_axis(X, 0.4*amp*math.cos(phs)) @ rig.dir0(n)
        info = {}
        for s in 'LR':
            d = self.side[s]
            hip = ppos+prot@self.rel['thigh.'+s]
            zoff, lift, splay, ph, stance = self.traj(t, s)
            abase = d['ank']
            h0 = math.hypot(abase[0]+splay-hip[0], abase[2]+zoff-hip[2])
            budget = (hip[1]-abase[1])-math.sqrt(max(d['D25']**2-h0*h0, 0.0))
            if not stance:
                lift = min(lift*lift_scale, max(budget, 0.0))
            ankle = np.array([abase[0]+splay, abase[1]+lift, abase[2]+zoff])
            knee, fdir = self._ik(s, hip, ankle)
            heads['thigh.'+s] = hip; heads['shin.'+s] = knee; heads['foot.'+s] = ankle
            dirs['foot.'+s] = fdir            # toes keep their rest splay: rigid follow of the foot
            dirs['thigh.'+s] = knee-hip; dirs['shin.'+s] = ankle-knee
            info[s] = dict(lift=float(lift), zoff=float(zoff), stance=stance, ph=ph,
                           hip=hip, ankle=ankle, budget=float(budget),
                           D=float(np.linalg.norm(ankle-hip)))
        return heads, dirs, info

    def _ik(self, s, hip, ankle):
        d = self.side[s]; t1, t2 = d['t'], d['sh']
        ax = ankle-hip; L = float(np.linalg.norm(ax)); over = max(0.0, L-d['D0'])
        if L > d['D0']: ax = ax/L*d['D0']; L = d['D0']
        u = ax/L
        a = (t1*t1-t2*t2+L*L)/(2*L); h = math.sqrt(max(t1*t1-a*a, 0.0))
        pole = FWD-np.dot(FWD, u)*u
        if np.linalg.norm(pole) < 1e-6: pole = X-np.dot(X, u)*u
        pole /= np.linalg.norm(pole)
        return hip+u*a+pole*h, d['fdir']

    # ---------- probes ----------
    def probe(self):
        out = dict(knee={'L': [], 'R': []}, pel=[], lift={'L': [], 'R': []},
                   footz={'L': [], 'R': []}, over={'L': [], 'R': []}, stance={'L': [], 'R': []})
        for f in range(NF):
            t = f/float(NF-1)
            heads, dirs, info = self.frame(t)
            out['pel'].append(float(heads['pelvis'][1]))
            for s in 'LR':
                td = heads['shin.'+s]-heads['thigh.'+s]
                sd = heads['foot.'+s]-heads['shin.'+s]
                c = float(np.dot(td/np.linalg.norm(td), sd/np.linalg.norm(sd)))
                out['knee'][s].append(math.degrees(math.acos(max(-1., min(1., c)))))
                out['lift'][s].append(info[s]['lift'])
                out['footz'][s].append(float(info[s]['ankle'][2]))
                out['over'][s].append(max(0.0, info[s]['D']-self.side[s]['D0']))
                out['stance'][s].append(info[s]['stance'])
        return out

    def summary(self):
        r = self.probe()
        q = dict(knee=max(max(r['knee']['L']), max(r['knee']['R'])),
                 pel=(min(r['pel']), max(r['pel'])),
                 clr={s: max(r['lift'][s]) for s in 'LR'},
                 over=max(max(r['over']['L']), max(r['over']['R'])))
        trav = {}
        for s in 'LR':
            fz = r['footz'][s]; steps = []
            for i in range(len(fz)-1):
                if r['stance'][s][i] and r['stance'][s][i+1]:
                    steps.append(fz[i+1]-fz[i])
            trav[s] = -sum(steps)
            q['dev_'+s] = max(abs(d-numpy_mean(steps)) for d in steps)/abs(numpy_mean(steps))
        q['trav'] = trav
        q['clr_min'] = min(q['clr']['L'], q['clr']['R'])
        return q


KEEP32 = ['root', 'pelvis', 'spine', 'chest', 'neck', 'head',
          'shoulder.L', 'upper_arm.L', 'forearm.L', 'hand.L',
          'shoulder.R', 'upper_arm.R', 'forearm.R', 'hand.R',
          'tail.001', 'tail.002', 'tail.003', 'tail.004', 'tail.005', 'tail.006',
          'thigh.L', 'shin.L', 'foot.L', 'toe.01.L', 'toe.02.L', 'toe.03.L',
          'thigh.R', 'shin.R', 'foot.R', 'toe.01.R', 'toe.02.R', 'toe.03.R']


def numpy_mean(a): return float(sum(a))/len(a)


def emit(w, path):
    """33 frames x 32 bones matrix_basis (bone-local, frame invariant -> fed to Blender as-is)."""
    rig, m = w.rig, w.rig.m
    frames = []
    for f in range(NF):
        heads, dirs, info = w.frame(f/float(NF-1))
        _ch, W1 = rig.solve(dirs=dirs, heads=heads)
        fr = {}
        for n in KEEP32:
            j = rig.joint_of[n]; p = m.par.get(j)
            loc = (np.linalg.inv(W1[p]) @ W1[j]) if p is not None else W1[j]
            B = np.linalg.inv(rig.L0[j]) @ loc
            fr[n] = [round(float(x), 9) for x in B.reshape(16)]
        frames.append(fr)
    frames[-1] = dict(frames[0])          # exact loop closure: f33 bit-identical to f1
    json.dump(dict(fps=30, nf=NF, bones=KEEP32, frames=frames), open(path, 'w'))
    print('emitted %s  %d frames x %d bones' % (path, len(frames), len(KEEP32)))


def mesh_report(w):
    """Skin the shipped GLB with the generated pose: shell seam per frame + lowest vertex."""
    rig = w.rig
    SA, SB = rig.sets('L'), rig.sets('R')
    rows = []
    for f in range(NF):
        heads, dirs, info = w.frame(f/float(NF-1))
        ch, W1 = rig.solve(dirs=dirs, heads=heads)
        V = rig.verts(ch)
        dL, pL = min_pair_dist(V[SA[0]], V[SA[1]])
        dR, pR = min_pair_dist(V[SB[0]], V[SB[1]])
        rows.append((f+1, dL, dR, float(V[:, 1].min()), knee_deg(rig, W1, 'L'), knee_deg(rig, W1, 'R')))
    return rows


def main():
    args = sys.argv[1:]
    rig = Rig(GLB)
    pf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_walkparams.json')
    w = Walk(rig, json.load(open(pf)) if os.path.exists(pf) else None)
    q = w.summary()
    print('params', {k: round(v, 5) for k, v in w.p.items()})
    print('knee peak %.2f deg | pelvis %.4f..%.4f | clearance L %.4f R %.4f | over %.4f'
          % (q['knee'], q['pel'][0], q['pel'][1], q['clr']['L'], q['clr']['R'], q['over']))
    print('stance travel L %.4f (dev %.1f%%) R %.4f (dev %.1f%%) | speed %.3f m/s'
          % (q['trav']['L'], 100*q['dev_L'], q['trav']['R'], 100*q['dev_R'],
             2*2*w.p['A']/((NF-1)/30.0)))
    r = w.probe()
    for f in range(NF):
        print('f%02d pel %.4f kneeL %5.2f kneeR %5.2f clrL %.4f clrR %.4f zL %.4f zR %.4f'
              % (f+1, r['pel'][f], r['knee']['L'][f], r['knee']['R'][f], r['lift']['L'][f],
                 r['lift']['R'][f], r['footz']['L'][f], r['footz']['R'][f]))
    if '--mesh' in args:
        print('--- skinned mesh (shipped GLB geometry) ---')
        worst = 0.0
        for f, dL, dR, mz, kL, kR in mesh_report(w):
            worst = max(worst, dL, dR)
            print('f%02d seamL %.4f seamR %.4f minz %+.4f kneeL %5.2f kneeR %5.2f'
                  % (f, dL, dR, mz, kL, kR))
        print('worst seam %.4f' % worst)
    if '--emit' in args:
        emit(w, args[args.index('--emit')+1])


if __name__ == '__main__':
    main()
