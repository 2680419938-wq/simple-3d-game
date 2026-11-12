# -*- coding: utf-8 -*-
"""Where can the ankle go while knee bend stays <= 25 deg, and what seam distance follows?"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib
from _glbpose import Rig, min_pair_dist, knee_deg

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
rig = Rig(GLB); m = rig.m
UP = np.array([0.,1.,0.]); FWD = np.array([0.,0.,1.])
AX = {s: rig.head0('thigh.'+s) - rig.head0('thigh.'+('R' if s=='L' else 'L')) for s in 'LR'}
LAT = {s: AX[s]/np.linalg.norm(AX[s]) for s in 'LR'}
LEG = {s: (float(np.linalg.norm(rig.head0('shin.'+s)-rig.head0('thigh.'+s))),
           float(np.linalg.norm(rig.head0('foot.'+s)-rig.head0('shin.'+s)))) for s in 'LR'}
LATR = {s: FWD - np.dot(FWD,LAT[s])*LAT[s] for s in 'LR'}   # lateral, in-plane with LAT(s), perpendicular to FWD? no: perpendicular to LAT
print('lens', {s: np.round(v,4) for s,v in LEG.items()}, 'dist(0deg)', {s: round(sum(v),4) for s,v in LEG.items()})

def dist_for_knee(s, th):
    t,s2 = LEG[s]
    return float(np.sqrt(t*t+s2*s2+2*t*s2*np.cos(np.radians(th))))

def build(s, ankle, foot_dir, hip=None):
    t,s2 = LEG[s]
    hip = rig.head0('thigh.'+s) if hip is None else hip
    axis = ankle-hip; L = np.linalg.norm(axis); ax = axis/L
    a = (t*t-s2*s2+L*L)/(2*L); h = np.sqrt(max(t*t-a*a,1e-12))
    n = FWD - np.dot(FWD,ax)*ax
    if np.linalg.norm(n) < 1e-6: n = LAT[s] - np.dot(LAT[s],ax)*ax
    n = n/np.linalg.norm(n)
    knee = hip + ax*a + n*h
    heads = {'thigh.'+s: hip, 'shin.'+s: knee, 'foot.'+s: ankle}
    dirs = {'thigh.'+s: knee-hip, 'shin.'+s: ankle-knee}
    prev = 'foot.'+s; p = ankle.copy()
    for b in ['toe.01.'+s,'toe.02.'+s,'toe.03.'+s]:
        p = p + foot_dir*np.linalg.norm(rig.head0(b)-rig.head0(prev)); heads[b]=p.copy(); prev=b
    for b in ['foot.'+s,'toe.01.'+s,'toe.02.'+s,'toe.03.'+s]: dirs[b]=foot_dir
    return heads, dirs

def measure(s, ankle, foot_dir=FWD, hip=None):
    h,d = build(s, ankle, foot_dir, hip)
    ch,W = rig.solve(d, heads=h)
    v = rig.verts(ch)
    A,B = rig.sets(s)
    gap, pair = min_pair_dist(v[A],v[B])
    return gap, knee_deg(rig,W,s), pair, v

for s in 'LR':
    print('=== side', s)
    for th in (0,25):
        D = dist_for_knee(s, th)
        rows=[]
        for fx in np.linspace(-1,1,9):
            for fl in np.linspace(-1,1,9):
                hor = np.hypot(fx,fl)
                if hor > 1: continue
                vz = -np.sqrt(max(1-hor*hor,0))
                ankle = rig.head0('thigh.'+s) + D*(FWD*fx + LAT[s]*fl + UP*vz)
                gap,knee,pair,_ = measure(s, ankle)
                rows.append((gap,fx,fl,knee))
        rows.sort()
        print(' knee<=%2d D=%.4f  best gaps (gap, fwd, lat):' % (th,D))
        for r in rows[:6]:
            print('    %.5f  fwd %+.2f lat %+.2f  knee %.2f' % (r[0],r[1],r[2],r[3]))
        worst = rows[-1]
        print('    worst %.5f fwd %+.2f lat %+.2f' % (worst[0],worst[1],worst[2]))
