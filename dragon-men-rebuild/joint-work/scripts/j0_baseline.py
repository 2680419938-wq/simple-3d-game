# -*- coding: utf-8 -*-
"""j0: baseline / post-build ray-occlusion table for body joints.

Per joint: bend about the flexion axis 0/30/60/90, twist about the bone axis 15/30/45,
plus a second bend axis 30/60/90 for twist-dominant joints (shoulder/neck/waist).
Two radii are reported: 0.06 (hand-work convention) and 1.15x the local skin radius
(clamped [0.06, 0.30]) because 0.06 lies INSIDE a thick limb and would hit the inner
wall regardless of any seam leak.
Usage: blender -b --factory-startup --python j0_baseline.py -- <blend> <out.json> [tag]
"""
import bpy, sys, os, json, math
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\joint-work\scripts')
import numpy as np
from mathutils import Vector
import jlib as J

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
BLD = ARGS[0] if ARGS else r'D:\ai\建模\dragon-men-rebuild\hand-work\ark\DragonMan_Hands_joint.blend'
OUT = ARGS[1] if len(ARGS) > 1 else r'D:\ai\建模\dragon-men-rebuild\joint-work\verify\baseline.json'
TAG = ARGS[2] if len(ARGS) > 2 else 'src'
NANG = 24
RAD06 = 0.06

bpy.ops.wm.open_mainfile(filepath=BLD)
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data_clear()
objs = [bpy.data.objects[n] for n in J.MESHES]
J.clear_pose(arm)
dg = bpy.context.evaluated_depsgraph_get()
skin_bvh = J.obj_bvh(objs, dg, mat_filter={J.SKIN})
bvh0 = J.obj_bvh(objs, dg)
res = {}
for key, cb, pb, tw in J.JOINTS:
    Jw, Ct = J.bh(arm, cb)
    u = J.unit(Ct - Jw)
    a1 = J.flex_axis(u)
    a2 = J.unit(np.cross(u, a1))
    rmed, nhit = J.local_radius(skin_bvh, Jw)
    rad = float(min(max(1.15 * rmed, RAD06), 0.30))
    poses = [('bend1', a1, d) for d in (0, 30, 60, 90)] + [('twist', u, d) for d in (15, 30, 45)]
    if tw:
        poses += [('bend2', a2, d) for d in (30, 60, 90)]
    rec = {'bone': cb, 'par': pb, 'J': Jw.tolist(), 'u': u.tolist(), 'a1': a1.tolist(),
           'rmed': round(rmed, 5), 'nhit': nhit, 'rad': round(rad, 5), 'twist': tw,
           'mt': J.mat_tally(objs, dg, Jw, max(0.10, 2.0 * rmed)), 'poses': {}}
    worst = 1.0
    worst6 = 1.0
    for pname, ax, deg in poses:
        J.set_rot(arm, cb, ax, deg)
        dgp = bpy.context.evaluated_depsgraph_get()
        bvh = J.obj_bvh(objs, dgp)
        Jp = np.array(arm.matrix_world @ arm.pose.bones[cb].head)
        dA = J.ring_dirs(ax, NANG)
        dB = J.ring_dirs(u, NANG)
        hA, mA = J.measure(bvh, Jp, dA, rad)
        hB, mB = J.measure(bvh, Jp, dB, rad)
        hA6, mA6 = J.measure(bvh, Jp, dA, RAD06)
        hB6, mB6 = J.measure(bvh, Jp, dB, RAD06)
        h = hA + hB
        h6 = hA6 + hB6
        rec['poses']['%s%d' % (pname, deg)] = dict(hA=hA, hB=hB, h=h, n=2 * NANG, rate=round(h / (2.0 * NANG), 4),
                                                   h6=h6, rate6=round(h6 / (2.0 * NANG), 4), missA=mA, missB=mB)
        worst = min(worst, h / (2.0 * NANG))
        worst6 = min(worst6, h6 / (2.0 * NANG))
    rec['worst'] = round(worst, 4)
    rec['worst06'] = round(worst6, 4)
    rec['mean'] = round(float(np.mean([p['rate'] for p in rec['poses'].values()])), 4)
    res[key] = rec
    print('[%s] %-11s rmed=%.4f rad=%.3f  ' % (TAG, key, rmed, rad) + ' '.join(
        '%s=%d%%' % (k, round(100 * v['rate'])) for k, v in rec['poses'].items()) +
        '  worst=%.0f%% worst06=%.0f%%' % (100 * worst, 100 * worst6), flush=True)
    print('       mats', rec['mt'], flush=True)
J.clear_pose(arm)
json.dump({'blend': BLD, 'nang': NANG, 'res': res}, open(OUT, 'w'), indent=1)
print('[%s] DONE -> %s' % (TAG, OUT))
