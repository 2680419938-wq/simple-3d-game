# -*- coding: utf-8 -*-
"""Feasibility: with knee <= 25 deg, which remaining DOF (ankle direction, foot pitch/roll) moves the L seam?"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib
from _glbpose import Rig, min_pair_dist, knee_deg

GLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
rig = Rig(GLB); m = rig.m
UP = np.array([0.,1.,0.]); FWD = np.array([0.,0.,1.])
AX = {s: rig.head0('thigh.'+s)-rig.head0('thigh.'+('R' if s=='L' else 'L')) for s in 'LR'}
E1 = {s: AX[s]/np.linalg.norm(AX[s]) for s in 'LR'}
LAT = {s: (E1[s]-np.dot(E1[s],FWD)*FWD)/np.linalg.norm(E1[s]-np.dot(E1[s],FWD)*FWD) for s in 'LR'}
LAT = {s: LAT[s]*np.sign(np.dot(LAT[s],E1[s])) for s in 'LR'}
print('basis L: fwd %s lat %s dot %.4f' % (np.round(FWD,3), np.round(LAT['L'],4), float(np.dot(FWD,LAT['L']))))
LEG = {s: (float(np.linalg.norm(rig.head0('shin.'+s)-rig.head0('thigh.'+s))),
           float(np.linalg.norm(rig.head0('foot.'+s)-rig.head0('shin.'+s)))) for s in 'LR'}

def build(s, ankle, foot_dir, hip=None):
    t, s2 = LEG[s]
    hip = rig.head0('thigh.'+s) if hip is None else hip
    axis = ankle-hip; L=np.linalg.norm(axis); ax=axis/L
    a=(t*t-s2*s2+L*L)/(2*L); h=np.sqrt(max(t*t-a*a,1e-12))
    n = FWD-np.dot(FWD,ax)*ax
    if np.linalg.norm(n)<1e-6: n = LAT[s]-np.dot(LAT[s],ax)*ax
    n/=np.linalg.norm(n)
    knee = hip+ax*a+n*h
    heads={'thigh.'+s:hip,'shin.'+s:knee,'foot.'+s:ankle}
    dirs={'thigh.'+s:knee-hip,'shin.'+s:ankle-knee}
    prev='foot.'+s; p=ankle.copy()
    for b in ['toe.01.'+s,'toe.02.'+s,'toe.03.'+s]:
        p = p+foot_dir*np.linalg.norm(rig.head0(b)-rig.head0(prev)); heads[b]=p.copy(); prev=b
    for b in ['foot.'+s,'toe.01.'+s,'toe.02.'+s,'toe.03.'+s]: dirs[b]=foot_dir
    return heads, dirs

def gap(s, ankle, foot_dir, hip=None):
    h,d = build(s, ankle, foot_dir, hip)
    ch,W = rig.solve(d, heads=h); v=rig.verts(ch)
    A,B = rig.sets(s)
    return min_pair_dist(v[A],v[B])[0], knee_deg(rig,W,s)

def ankle_at(s, knee_target, fwd=0.0, lat=0.0):
    t,s2 = LEG[s]
    D = float(np.sqrt(t*t+s2*s2+2*t*s2*np.cos(np.radians(knee_target))))
    h = np.array([fwd,lat]); hr = np.hypot(fwd,lat)
    if hr > D*0.98: h *= D*0.98/hr; hr = D*0.98
    vz = -np.sqrt(max(D*D-fwd*fwd-lat*lat,0))
    return rig.head0('thigh.'+s) + FWD*fwd + LAT[s]*lat + UP*vz

for s in 'LR':
    print('=== side', s)
    print('  ankle-direction sweep at knee 25 (foot flat):')
    for fwd in (-0.09,-0.045,0,0.045,0.09):
        row=[]
        for lat in (-0.09,-0.045,0,0.045,0.09):
            g,k = gap(s, ankle_at(s,25,fwd,lat), FWD)
            row.append('%6.4f' % g)
        print('    fwd %+.3f: %s' % (fwd, ' '.join(row)))
    print('  foot pitch sweep (ankle straight under hip, knee 25):')
    for pitch in (-60,-45,-30,-20,-10,0,10,20,30,45,60):
        fd = FWD*np.cos(np.radians(pitch)) + UP*np.sin(np.radians(pitch))
        g,k = gap(s, ankle_at(s,25,0,0), fd)
        print('    pitch %+4d -> gap %.5f' % (pitch,g))
    print('  foot twist sweep (pitch 0, yaw about shin axis):')
    for tw in (-40,-25,-10,0,10,25,40):
        c,sn = np.cos(np.radians(tw)), np.sin(np.radians(tw))
        fd = FWD*c + LAT[s]*sn
        g,k = gap(s, ankle_at(s,25,0,0), fd)
        print('    twist %+4d -> gap %.5f' % (tw,g))
