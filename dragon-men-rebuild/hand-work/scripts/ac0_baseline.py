
# -*- coding: utf-8 -*-
"""Baseline: does the SOURCE hand leak at each finger joint when bent 0/30/60/90? + closeup renders."""
import bpy, sys, os, json, math
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\hand-work\scripts')
import numpy as np
from mathutils import Vector
import raylib as RL

SRC = r'D:\ai\建模\dragon-men-rebuild\std-rig\DragonMan_Std_TPose.blend'
OUT = r'D:\ai\建模\dragon-men-rebuild\hand-work\verify\baseline_rays.json'
RDIR = r'D:\ai\建模\dragon-men-rebuild\hand-work\renders'
os.makedirs(RDIR, exist_ok=True)
RAD = 0.06
NANG = 24

bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data: arm.animation_data_clear()
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('DragonMan')]
print('[B] meshes', [o.name for o in meshes])
J = [t for t in RL.joint_list(arm)]
res = {}
tot = hitn = 0
for side, tag, f, k, nm, par in J:
    laxW = None
    rec = {}
    for deg in (0, 30, 60, 90):
        RL.set_bend(arm, side, f, k, deg)
        dg = bpy.context.evaluated_depsgraph_get()
        bvh = RL.world_bvh(meshes, dg)
        Jp = np.array(arm.matrix_world @ arm.pose.bones[nm].head)
        _, axW = RL.flex_axis(arm, side, f, k)
        axW = np.array(axW)
        # ring A: perpendicular to the flexion (hinge) axis -> the plane the crack opens in
        ea = np.array([0.0, 0, 1.0]) if abs(axW[2]) < 0.9 else np.array([1.0, 0, 0])
        uA = np.cross(axW, ea); uA /= np.linalg.norm(uA); vA = np.cross(axW, uA)
        # ring B: perpendicular to the bent bone's rest axis
        br = np.array(arm.data.bones[nm].tail_local - arm.data.bones[nm].head_local)
        br = (np.array(arm.matrix_world.to_3x3()) @ br); br /= np.linalg.norm(br)
        uB = np.cross(br, ea); uB /= np.linalg.norm(uB); vB = np.cross(br, uB)
        hA, missA, _ = RL.measure_joint(bvh, Jp, RL.ring_dirs(uA, vA, NANG), RAD)
        hB, missB, _ = RL.measure_joint(bvh, Jp, RL.ring_dirs(uB, vB, NANG), RAD)
        rec[deg] = {'hA': hA, 'hB': hB, 'n': NANG, 'missA': missA, 'missB': missB}
        tot += 2 * NANG; hitn += hA + hB
    res['%s/%s%d' % (tag, f, k)] = rec
    print('[B] %-12s ' % ('%s %s%d' % (tag, f, k)) + ' '.join(
        '%d:%.0f%%/%.0f%%' % (d, 100.0 * rec[d]['hA'] / NANG, 100.0 * rec[d]['hB'] / NANG) for d in (0, 30, 60, 90)))
print('[B] overall hit rate %.4f (%d/%d)' % (hitn / tot, hitn, tot))
worst = min(min(v['hA'], v['hB']) for v in res.values() for v in v.values())
print('[B] worst single ring %d/%d' % (worst, NANG))
json.dump({'rad': RAD, 'nang': NANG, 'res': res, 'overall': hitn / tot}, open(OUT, 'w'), indent=1)

# closeup renders of the left index finger at 0/30/60/90
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 24; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 700
cam_d = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('C', cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.type = 'ORTHO'
sd = bpy.data.lights.new('S', 'SUN'); sd.energy = 4.0
sun = bpy.data.objects.new('S', sd); sc.collection.objects.link(sun); sun.rotation_euler = (math.radians(55), 0, math.radians(35))
sd2 = bpy.data.lights.new('F', 'SUN'); sd2.energy = 2.0
f2 = bpy.data.objects.new('F', sd2); sc.collection.objects.link(f2); f2.rotation_euler = (math.radians(70), 0, math.radians(-120))
hb = arm.data.bones['mixamorig:LeftHand']
pn = (hb.tail_local - hb.head_local).normalized()
p1 = arm.data.bones['mixamorig:LeftHandIndex1']; p3 = arm.data.bones['mixamorig:LeftHandIndex3']
fdir = (p3.tail_local - p1.head_local).normalized()
side_dir = Vector((0, 0, 1)).cross(Vector(fdir))
if side_dir.length < 1e-4: side_dir = Vector((1, 0, 0))
side_dir.normalize()
mid = (p1.head_local + p3.tail_local) / 2
ctr = arm.matrix_world @ mid
for deg in (0, 30, 60, 90):
    RL.set_bend(arm, 'Left', 'Index', 2, deg)
    d = Vector((1, 0, 0))
    cam_d.ortho_scale = 0.20
    cam.location = ctr + d * 4
    cam.rotation_euler = (ctr - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(RDIR, 'base_Lidx2_bend%d.png' % deg)
    bpy.ops.render.render(write_still=True)
    print('[B] render', deg, flush=True)
RL.clear_pose(arm)
print('[B] DONE')
