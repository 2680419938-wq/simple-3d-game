
# -*- coding: utf-8 -*-
"""Post-build: per-joint 0/30/60/90 ray occlusion on the built blend (same convention as ac0_baseline)."""
import bpy, sys, os, json, math
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\hand-work\scripts')
import numpy as np
from mathutils import Vector
import raylib as RL

BLD = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else r'D:\ai\建模\dragon-men-rebuild\hand-work\ark\DragonMan_Hands_joint.blend'
OUT = sys.argv[sys.argv.index('--') + 2] if '--' in sys.argv and len(sys.argv) > sys.argv.index('--') + 2 else r'D:\ai\建模\dragon-men-rebuild\hand-work\verify\rays_joint.json'
RAD = 0.06
NANG = 24

bpy.ops.wm.open_mainfile(filepath=BLD)
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data_clear()
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('DragonMan')]
print('[R] meshes', [o.name for o in meshes])
res = {}
tot = hitn = 0
for side, tag, f, k, nm, par in RL.joint_list(arm):
    rec = {}
    for deg in (0, 30, 60, 90):
        RL.set_bend(arm, side, f, k, deg)
        dg = bpy.context.evaluated_depsgraph_get()
        bvh = RL.world_bvh(meshes, dg)
        Jp = np.array(arm.matrix_world @ arm.pose.bones[nm].head)
        _, axW = RL.flex_axis(arm, side, f, k)
        axW = np.array(axW)
        ea = np.array([0.0, 0, 1.0]) if abs(axW[2]) < 0.9 else np.array([1.0, 0, 0])
        uA = np.cross(axW, ea); uA /= np.linalg.norm(uA); vA = np.cross(axW, uA)
        br = np.array(arm.data.bones[nm].tail_local - arm.data.bones[nm].head_local)
        br = (np.array(arm.matrix_world.to_3x3()) @ br); br /= np.linalg.norm(br)
        uB = np.cross(br, ea); uB /= np.linalg.norm(uB); vB = np.cross(br, uB)
        hA, missA, _ = RL.measure_joint(bvh, Jp, RL.ring_dirs(uA, vA, NANG), RAD)
        hB, missB, _ = RL.measure_joint(bvh, Jp, RL.ring_dirs(uB, vB, NANG), RAD)
        rec[str(deg)] = {'hA': hA, 'hB': hB, 'n': NANG, 'missA': missA, 'missB': missB}
        tot += 2 * NANG
        hitn += hA + hB
    res['%s/%s%d' % (tag, f, k)] = rec
    print('[R] %-12s ' % ('%s %s%d' % (tag, f, k)) + ' '.join(
        '%d:%.0f%%/%.0f%%' % (d, 100.0 * rec[str(d)]['hA'] / NANG, 100.0 * rec[str(d)]['hB'] / NANG) for d in (0, 30, 60, 90)), flush=True)
print('[R] overall hit rate %.4f (%d/%d)' % (hitn / tot, hitn, tot))
worst = min(min(v['hA'], v['hB']) for v in res.values() for v in v.values())
print('[R] worst single ring %d/%d' % (worst, NANG))
miss_any = [(kk, d, v['missA'], v['missB']) for kk, r in res.items() for d, v in r.items() if v['missA'] or v['missB']]
print('[R] rings with misses:', len(miss_any))
for m in miss_any[:40]:
    print('   ', m)
json.dump({'rad': RAD, 'nang': NANG, 'blend': BLD, 'res': res, 'overall': hitn / tot, 'worst': worst}, open(OUT, 'w'), indent=1)
print('[R] DONE')
