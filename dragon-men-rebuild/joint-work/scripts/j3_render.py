# -*- coding: utf-8 -*-
"""j3: before/after closeup renders per joint at bend 90 (same camera/light for both tags).
Camera choices are computed ONCE on the source blend and reused (cams json), so BEFORE and
AFTER are pixel-comparable.
Usage: blender -b --python j3_render.py -- <blend> <TAG> <camjson> <outdir>
"""
import bpy, sys, os, json, math
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\joint-work\scripts')
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import jlib as J

ARGS = sys.argv[sys.argv.index('--') + 1:]
BLD, TAG, CAMJSON, OUTDIR = ARGS[0], ARGS[1], ARGS[2], ARGS[3]
BENDS = float(ARGS[4]) if len(ARGS) > 4 else 90.0
ONLY = ARGS[5].split(',') if len(ARGS) > 5 else None
BTAG = 'bend%d' % int(BENDS)
os.makedirs(OUTDIR, exist_ok=True)
BUILD = ['L_shoulder', 'R_shoulder', 'L_elbow', 'R_elbow', 'L_wrist', 'R_wrist',
         'L_hip', 'R_hip', 'neck', 'waist', 'waist1']
INFO = {k: (cb, pb) for k, cb, pb, tw in J.JOINTS}

bpy.ops.wm.open_mainfile(filepath=BLD)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
ACT = arm.animation_data.action if arm.animation_data else None
if ACT is not None:
    arm.animation_data.action = None
J.clear_pose(arm)
bpy.context.view_layer.update()
objs = [bpy.data.objects[n] for n in J.MESHES]
dg = bpy.context.evaluated_depsgraph_get()
skin = J.obj_bvh(objs, dg, mat_filter={J.SKIN})
allb = J.obj_bvh(objs, dg)

cams = json.load(open(CAMJSON)) if (TAG == 'AFTER' and os.path.exists(CAMJSON)) else {}
for key in BUILD:
    if key in cams:
        continue
    cb, pb = INFO[key]
    Jw, Ct = J.bh(arm, cb)
    u = J.unit(Ct - Jw)
    a1 = J.flex_axis(u)
    w = J.unit(np.cross(u, a1))
    rmed, _ = J.local_radius(skin, Jw)
    off = np.array(Jw) - np.array([-0.506, -0.5, Jw[2]])
    if np.dot(a1, off) < 0:
        a1 = -a1
    # gap side: which of +-w opens up when bent 90 deg
    def probe(sign):
        d = w * sign
        loc, no, idx, dr = allb.ray_cast(Vector(Jw), Vector(d), 0.9)
        dr = 0.9 if loc is None else dr
        return dr
    r_p, r_m = probe(1.0), probe(-1.0)
    J.set_rot(arm, cb, a1, 90.0)
    dgp = bpy.context.evaluated_depsgraph_get()
    allb2 = J.obj_bvh(objs, dgp)
    b_p = 0.9 if allb2.ray_cast(Vector(Jw), Vector(w), 0.9)[0] is None else allb2.ray_cast(Vector(Jw), Vector(w), 0.9)[3]
    b_m = 0.9 if allb2.ray_cast(Vector(Jw), Vector(-w), 0.9)[0] is None else allb2.ray_cast(Vector(Jw), Vector(-w), 0.9)[3]
    J.clear_pose(arm)
    bpy.context.view_layer.update()
    sign = 1.0 if (b_p - r_p) >= (b_m - r_m) else -1.0
    cams[key] = dict(J=[float(x) for x in Jw], u=[float(x) for x in u], a1=[float(x) for x in a1],
                     w=[float(x) for x in w * sign], med=round(rmed, 5),
                     side=[float(x) for x in a1], front=[float(x) for x in (w * sign)],
                     scale_side=round(max(0.10, 7.0 * rmed), 4), scale_front=round(max(0.045, 4.4 * rmed), 4),
                     gap=[round(r_p, 4), round(r_m, 4), round(b_p, 4), round(b_m, 4)])
    print('[C] %-11s med=%.4f gap probe %s -> front sign %.0f' % (key, rmed, cams[key]['gap'], sign), flush=True)
json.dump(cams, open(CAMJSON, 'w'), indent=1)

sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 24
sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 640
sc.render.image_settings.file_format = 'PNG'
cam_d = bpy.data.cameras.new('CAM')
cam = bpy.data.objects.new('CAM', cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam_d.type = 'ORTHO'
for i, e in enumerate((7.0, 3.5)):
    sd = bpy.data.lights.new('S%d' % i, 'SUN')
    sd.energy = e
    sd.angle = math.radians(12)
    so = bpy.data.objects.new('S%d' % i, sd)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(52), 0, math.radians(35 + 100 * i))
w = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.05, 0.055, 0.07, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 0.55
bpy.context.view_layer.update()


def shoot(name, ctr, d, scale):
    cam_d.ortho_scale = scale
    cam.location = Vector(ctr) + Vector(d).normalized() * 6.0
    cam.rotation_euler = (Vector(ctr) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    sc.render.filepath = os.path.join(OUTDIR, name)
    bpy.ops.render.render(write_still=True)
    print('[C] render', name, flush=True)


for key in (ONLY or BUILD):
    c = cams[key]
    cb, pb = INFO[key]
    J.set_rot(arm, cb, np.array(c['a1']), BENDS)
    bpy.context.view_layer.update()
    for suf, d, scl in (('side', c['side'], c['scale_side']), ('front', c['front'], c['scale_front'])):
        shoot('seam%s_%s_%s_%s.png' % (TAG, key, BTAG, suf), c['J'], d, scl)
    J.clear_pose(arm)
    bpy.context.view_layer.update()
print('[C] DONE', TAG, OUTDIR)
