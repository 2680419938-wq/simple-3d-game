
# -*- coding: utf-8 -*-
"""ac5 renders. No args: full-hand bend views of the built blend.
   With '-- <blend> <prefix>': seam comparison shots (same camera for src vs built)."""
import bpy, sys, os, math
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\hand-work\scripts')
import numpy as np
from mathutils import Vector, Quaternion
import raylib as RL

HW = r'D:\ai\建模\dragon-men-rebuild\hand-work'
RDIR = os.path.join(HW, 'renders')
os.makedirs(RDIR, exist_ok=True)
FING = ('Thumb', 'Index', 'Middle', 'Ring')
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SEAM = bool(ARGS)
BLD = ARGS[0] if SEAM else os.path.join(HW, 'ark', 'DragonMan_Hands_joint.blend')
PREFIX = ARGS[1] if len(ARGS) > 1 else 'seam'

bpy.ops.wm.open_mainfile(filepath=BLD)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data_clear()
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 32; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 800
sc.render.film_transparent = False
cam_d = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('C', cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.type = 'ORTHO'
sd = bpy.data.lights.new('S', 'SUN'); sd.energy = 4.0
sun = bpy.data.objects.new('S', sd); sc.collection.objects.link(sun); sun.rotation_euler = (math.radians(55), 0, math.radians(35))
sd2 = bpy.data.lights.new('F', 'SUN'); sd2.energy = 2.0
f2 = bpy.data.objects.new('F', sd2); sc.collection.objects.link(f2); f2.rotation_euler = (math.radians(70), 0, math.radians(-120))
bpy.context.view_layer.update()


def setj(side, f, k, deg):
    lax, _ = RL.flex_axis(arm, side, f, k)
    pb = arm.pose.bones['mixamorig:%sHand%s%d' % (side, f, k)]
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = Quaternion(lax, math.radians(deg)) if deg else Quaternion((1, 0, 0, 0))


def curl(side, deg):
    RL.clear_pose(arm)
    for f in FING:
        for k in (1, 2, 3):
            setj(side, f, k, deg)
    bpy.context.view_layer.update()


def shoot(path, ctr, d, scale):
    cam_d.ortho_scale = scale
    cam.location = Vector(ctr) + Vector(d) * 3.0
    cam.rotation_euler = (Vector(ctr) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[P] render', os.path.basename(path), flush=True)


def hand_of(side):
    pts = []
    for f in FING:
        for k in (1, 2, 3):
            b = arm.data.bones['mixamorig:%sHand%s%d' % (side, f, k)]
            pts.append(arm.matrix_world @ b.head_local)
            pts.append(arm.matrix_world @ b.tail_local)
    P = np.array([[p.x, p.y, p.z] for p in pts])
    return P.mean(axis=0), P


if SEAM:
    for (side, f, k) in (('Left', 'Index', 2), ('Left', 'Index', 1), ('Right', 'Ring', 2)):
        tag = ('L' if side == 'Left' else 'R') + f[0].lower() + ('idx' if f == 'Index' else '') + str(k)
        bn = arm.data.bones['mixamorig:%sHand%s%d' % (side, f, k)]
        J = np.array(list(arm.matrix_world @ bn.head_local))
        ch = arm.data.bones['mixamorig:%sHand%s%d' % (side, f, k + 1)]
        u = np.array(list(arm.matrix_world @ ch.tail_local)) - np.array(list(arm.matrix_world @ ch.head_local))
        u /= np.linalg.norm(u)
        lax, ax = RL.flex_axis(arm, side, f, k)
        ax = np.array(list(arm.matrix_world.to_3x3() @ ax)); ax /= np.linalg.norm(ax)
        n = np.cross(u, ax); n /= np.linalg.norm(n)
        for deg in (0, 60, 90):
            RL.clear_pose(arm)
            setj(side, f, k, deg)
            bpy.context.view_layer.update()
            shoot(os.path.join(RDIR, '%s_%s_bend%d_side.png' % (PREFIX, tag, deg)), J, ax, 0.10)
            shoot(os.path.join(RDIR, '%s_%s_bend%d_dorsal.png' % (PREFIX, tag, deg)), J, -n, 0.10)
else:
    for side, tag in (('Left', 'L'), ('Right', 'R')):
        ctr, P = hand_of(side)
        RL.clear_pose(arm); bpy.context.view_layer.update()
        t0 = np.array(list(arm.matrix_world @ arm.pose.bones['mixamorig:%sHandIndex3' % side].tail))
        curl(side, 90)
        t1 = np.array(list(arm.matrix_world @ arm.pose.bones['mixamorig:%sHandIndex3' % side].tail))
        pn = (t1 - t0) / np.linalg.norm(t1 - t0)
        print('[P] %s palm_dir %s' % (side, np.round(pn, 3)))
        for deg in (0, 45, 90):
            curl(side, deg)
            for lbl, d in (('palm', pn), ('back', -pn)):
                shoot(os.path.join(RDIR, 'hand_%s_bend%d_%s.png' % (tag, deg, lbl)), ctr, d, 0.46)
        curl(side, 90)
        b1 = arm.data.bones['mixamorig:%sHandIndex1' % side]
        b3 = arm.data.bones['mixamorig:%sHandIndex3' % side]
        c2 = (np.array(list(arm.matrix_world @ b1.head_local)) + np.array(list(arm.matrix_world @ b3.tail_local))) / 2
        shoot(os.path.join(RDIR, 'zoom_%s_index90_side.png' % tag), c2, np.cross(pn, [0, 0, 1.0]), 0.20)
RL.clear_pose(arm)
print('[P] DONE')
