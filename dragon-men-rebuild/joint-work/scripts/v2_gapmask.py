# -*- coding: utf-8 -*-
"""Gap mask diagnostic: where does the hip opening show background? Radii around J gate the crack.
Usage: blender -b --factory-startup --python v2_gapmask.py -- <blend> <camjson> <outjson> [KEY]
"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import jlib as JL

A = sys.argv[sys.argv.index('--') + 1:]
BLD, CAMJSON, OUT = A[0], A[1], A[2]
KEY = A[3] if len(A) > 3 else 'R_hip'
cams = json.load(open(CAMJSON, encoding='utf-8'))
INFO = {k: (cb, pb) for k, cb, pb, tw in JL.JOINTS}
c = cams[KEY]
J = np.array(c['J'], dtype=np.float64)
N = 320
bpy.ops.wm.open_mainfile(filepath=BLD)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data.action = None
JL.clear_pose(arm)
objs = [bpy.data.objects[n] for n in JL.MESHES]
body = bpy.data.objects['DragonMan_Body']
co = np.empty(len(body.data.vertices) * 3); body.data.vertices.foreach_get('co', co)
MW = np.array(body.matrix_world)
W0 = co.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
polys = [tuple(p.vertices) for p in body.data.polygons]
tris, own = [], []
for i, p in enumerate(polys):
    for k in range(1, len(p) - 1):
        tris.append((p[0], p[k], p[k + 1])); own.append(i)
print('[M] tris', len(tris), flush=True)
tre = [tuple(x) for x in W0]

cam_d = bpy.data.cameras.new('CAM'); cam_d.type = 'ORTHO'
cam = bpy.data.objects.new('CAM', cam_d); sc.collection.objects.link(cam); sc.camera = cam
res = {'key': KEY, 'rows': {}}
ts = [0.030, 0.052, 0.080, 0.120]
for bend in (0.0, 30.0, 60.0, 90.0):
    JL.clear_pose(arm)
    JL.set_rot(arm, INFO[KEY][0], np.array(c['a1']), bend)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    obe = body.evaluated_get(dg)
    m2 = obe.to_mesh()
    V = np.empty(len(m2.vertices) * 3); m2.vertices.foreach_get('co', V)
    V = V.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
    obe.to_mesh_clear()
    bvh = BVHTree.FromPolygons([tuple(x) for x in V], tris, all_triangles=True)
    for suf in ('front',):
        if suf == 'sf':
            cam_d.ortho_scale = float(c['scale_front'])
            dvec = Vector(c['front']).normalized()
        else:
            cam_d.ortho_scale = float(c['scale_' + suf])
            dvec = Vector(c[suf]).normalized()
        cam.location = Vector(J) + dvec * 6.0
        cam.rotation_euler = (Vector(J) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
        bpy.context.view_layer.update()
        od = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
        img = np.zeros((N, N, 4), np.float32); img[..., 3] = 1.0
        st = {'total': N * N, 'bg': 0, 'near': {str(t): 0 for t in ts}}
        for py in range(N):
            for px in range(N):
                nx = (px + 0.5) / N; ny = (py + 0.5) / N
                o = cam.matrix_world @ Vector(((nx - 0.5) * cam_d.ortho_scale, (ny - 0.5) * cam_d.ortho_scale, 0.0))
                h = bvh.ray_cast(o, od, 12.0)
                if h[0] is not None:
                    mine = min(polys[own[h[2]]]) >= 21870
                    img[py, px, 0] = 0.30; img[py, px, 1] = 0.30; img[py, px, 2] = 0.42
                    if mine:
                        img[py, px, 0] = 0.95; img[py, px, 1] = 0.55; img[py, px, 2] = 0.05
                    continue
                st['bg'] += 1
                s = float(od.dot(Vector(J - o)))
                pp = (np.array(o) + s * np.array(od)) - J
                dJ = float(np.linalg.norm(pp))
                img[py, px, 0] = 0.12; img[py, px, 1] = 0.42; img[py, px, 2] = 0.12
                for tt in ts:
                    if dJ < tt:
                        st['near'][str(tt)] += 1
                        if tt == 0.052:
                            img[py, px, 0] = 0.95; img[py, px, 1] = 0.10; img[py, px, 2] = 0.10
        tag = 'bend%d_%s' % (int(bend), suf)
        im = bpy.data.images.new('m_' + tag, N, N)
        im.pixels.foreach_set(img[::-1].ravel())
        PD = os.path.join(os.path.dirname(OUT), '..', 'renders', 'v2', 'probe')
        os.makedirs(PD, exist_ok=True)
        im.filepath_raw = os.path.join(PD, 'gap_%s_%s.png' % (KEY, tag)); im.file_format = 'PNG'; im.save()
        res['rows'][tag] = st
        print('[M] %-6s %-5s bg=%d nearJ %s' % ('bend%d' % int(bend), suf, st['bg'], st['near']), flush=True)
JL.clear_pose(arm)
json.dump(res, open(OUT, 'w'), indent=1)
print('[M] DONE', flush=True)
