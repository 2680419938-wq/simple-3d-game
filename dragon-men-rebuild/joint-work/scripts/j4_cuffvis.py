# -*- coding: utf-8 -*-
"""j4 (diagnostic only, never saved): x-ray the body (gray, alpha .18) and paint the NEW cuff
faces bright red, at the same cameras as j3, to see where the cuffs actually sit at bend 90.
"""
import bpy, sys, os, json, math
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\joint-work\scripts')
import numpy as np
from mathutils import Vector
import jlib as J

ARGS = sys.argv[sys.argv.index('--') + 1:]
BLD, CAMJSON, OUTDIR, NP0 = ARGS[0], ARGS[1], ARGS[2], int(ARGS[3])
os.makedirs(OUTDIR, exist_ok=True)
BUILD = ['L_shoulder', 'R_shoulder', 'L_elbow', 'R_elbow', 'L_wrist', 'R_wrist',
         'L_hip', 'R_hip', 'neck', 'waist', 'waist1']
INFO = {k: (cb, pb) for k, cb, pb, tw in J.JOINTS}
cams = json.load(open(CAMJSON))

bpy.ops.wm.open_mainfile(filepath=BLD)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data.action = None
J.clear_pose(arm)
gmat = bpy.data.materials.new('XGRAY')
gmat.use_nodes = True
gmat.blend_method = 'BLEND'
b = gmat.node_tree.nodes['Principled BSDF']
b.inputs['Base Color'].default_value = (0.55, 0.57, 0.62, 1)
b.inputs['Alpha'].default_value = 0.16
b.inputs['Roughness'].default_value = 0.6
rmat = bpy.data.materials.new('XRED')
rmat.use_nodes = True
rb = rmat.node_tree.nodes['Principled BSDF']
rb.inputs['Base Color'].default_value = (1.0, 0.05, 0.02, 1)
rb.inputs['Emission Color'].default_value = (1.0, 0.15, 0.05, 1)
rb.inputs['Emission Strength'].default_value = 0.6
body = bpy.data.objects['DragonMan_Body']
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.startswith('DragonMan'):
        o.data.materials.clear()
        o.data.materials.append(gmat)
body.data.materials.append(rmat)
me = body.data
ri = len(me.materials) - 1
n = 0
for p in me.polygons:
    if p.index >= NP0:
        p.material_index = ri
        n += 1
print('[X] red faces', n, 'poly0', NP0, 'total', len(me.polygons), flush=True)

sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 24
sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 640
sc.render.film_transparent = False
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
w.node_tree.nodes['Background'].inputs[1].default_value = 0.5


def shoot(name, ctr, d, scale):
    cam_d.ortho_scale = scale
    cam.location = Vector(ctr) + Vector(d).normalized() * 6.0
    cam.rotation_euler = (Vector(ctr) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    sc.render.filepath = os.path.join(OUTDIR, name)
    bpy.ops.render.render(write_still=True)
    print('[X] render', name, flush=True)


for key in BUILD:
    c = cams[key]
    cb, pb = INFO[key]
    for suf, d in (('side', c['side']), ('front', c['front'])):
        J.set_rot(arm, cb, np.array(c['a1']), 90.0)
        bpy.context.view_layer.update()
        shoot('cuffvis_%s_bend90_%s.png' % (key, suf), c['J'], d,
              c['scale_side'] if suf == 'side' else c['scale_front'])
        J.clear_pose(arm)
        bpy.context.view_layer.update()
print('[X] DONE')
