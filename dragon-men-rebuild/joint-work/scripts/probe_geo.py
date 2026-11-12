# -*- coding: utf-8 -*-
"""Probe: weight/geometry layout at candidate joints + orientation renders."""
import bpy, sys, os, json, math
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\joint-work\scripts')
import numpy as np
from mathutils import Vector
import jlib as J

SRC = r'D:\ai\建模\dragon-men-rebuild\hand-work\ark\DragonMan_Hands_joint.blend'
RD = r'D:\ai\建模\dragon-men-rebuild\joint-work\renders'
os.makedirs(RD, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data_clear()
J.clear_pose(arm)
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
grp = {g.index: g.name for g in body.vertex_groups}
dom = []
for v in me.vertices:
    if len(v.groups):
        bg = max(v.groups, key=lambda g: g.weight)
        dom.append(grp.get(bg.group, ''))
    else:
        dom.append('')
dom = np.array(dom)
print('[P] z-slice dominant groups (body)')
for z0 in np.arange(0.55, 1.65, 0.05):
    m = (co[:, 2] >= z0) & (co[:, 2] < z0 + 0.05)
    if m.sum() == 0:
        continue
    u, c = np.unique(dom[m], return_counts=True)
    order = np.argsort(-c)[:4]
    print('  z %.2f n=%5d  ' % (z0, m.sum()) + '  '.join('%s:%d' % (u[i].replace('mixamorig:', ''), c[i]) for i in order))

objs = [bpy.data.objects[n] for n in J.MESHES]
dg = bpy.context.evaluated_depsgraph_get()
skin = J.obj_bvh(objs, dg, mat_filter={J.SKIN})
allb = J.obj_bvh(objs, dg)
print('[P] axis distances from each candidate joint (skin, world)')
for key, cb, pb, tw in J.JOINTS:
    Jw, Ct = J.bh(arm, cb)
    line = []
    for ax, nm in ((np.array([1.0, 0, 0]), '+X'), (np.array([-1.0, 0, 0]), '-X'),
                   (np.array([0, 1.0, 0]), '+Y'), (np.array([0, -1.0, 0]), '-Y'),
                   (np.array([0, 0, 1.0]), '+Z'), (np.array([0, 0, -1.0]), '-Z')):
        loc, no, idx, d = skin.ray_cast(Vector(Jw), Vector(ax), 1.0)
        line.append('%s=%s' % (nm, ('%.3f' % d) if loc is not None else 'none'))
    print('  %-11s J=(%.3f,%.3f,%.3f) %s' % (key, Jw[0], Jw[1], Jw[2], ' '.join(line)))

sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 20; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 640
cam_d = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('C', cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.type = 'ORTHO'
for i, e in enumerate((6.0, 3.0)):
    sd = bpy.data.lights.new('S%d' % i, 'SUN'); sd.energy = e
    so = bpy.data.objects.new('S%d' % i, sd); sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(55), 0, math.radians(35 + 90 * i))
bpy.context.view_layer.update()


def shoot(name, ctr, d, scale):
    cam_d.ortho_scale = scale
    cam.location = Vector(ctr) + Vector(d) * 5.0
    cam.rotation_euler = (Vector(ctr) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    sc.render.filepath = os.path.join(RD, name)
    bpy.ops.render.render(write_still=True)
    print('[P] render', name, flush=True)


shoot('probe_front.png', (0.2, -0.5, 1.0), (-1, 0, 0), 2.4)
shoot('probe_side.png', (0.2, -0.5, 1.0), (0, -1, 0), 2.4)
shoot('probe_neck_side.png', (-0.45, -0.5, 1.35), (0, -1, 0), 0.55)
shoot('probe_neck_front.png', (-0.45, -0.5, 1.35), (-1, 0, 0), 0.55)
shoot('probe_hip_side.png', (-0.56, -0.40, 0.55), (0, -1, 0), 0.55)
shoot('probe_shoulder_up.png', (-0.45, -0.70, 1.20), (-1, 0, 0), 0.60)
print('[P] DONE')
