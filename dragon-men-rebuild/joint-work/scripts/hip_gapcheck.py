# -*- coding: utf-8 -*-
"""Does the shrunken hip socket still plug the open crotch at bend? Counterfactual measurement:
for each camera ray, compare the first hit WITH the socket faces and with them removed (i.e. the
unplugged mesh). Rays whose first hit changes to background or to a back-face are exactly the pixels
the socket is responsible for.
Usage: blender -b --factory-startup --python hip_gapcheck.py -- <blend> <camjson> <out.json> <tag>
"""
import bpy, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import jlib as J

A = sys.argv[sys.argv.index('--') + 1:]
BLD, CAMJSON, OUT, TAG = A[0], A[1], A[2], A[3]
SCRIPT = os.path.dirname(os.path.abspath(__file__))
BR = json.load(open(os.path.join(SCRIPT, '..', 'verify', 'build_report.json'), encoding='utf-8'))
N0P = 23206
cams = json.load(open(CAMJSON))
INFO = {k: (cb, pb) for k, cb, pb, tw in J.JOINTS}

bpy.ops.wm.open_mainfile(filepath=BLD)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data.action = None
J.clear_pose(arm)
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
co = np.array([list(v.co) for v in me.vertices], dtype=np.float64)
W = co @ MW[:3, :3].T + MW[:3, 3]
polys = [tuple(p.vertices) for p in me.polygons]
sock = {}
for jd in BR['joints']:
    if jd['nv_s'] > 0:
        continue
    base, nvp = int(jd['base']), int(jd['nvp'])
    sock[jd['key']] = set(range(base, base + nvp))
is_sock = [False] * len(polys)
for k, vs in sock.items():
    for i, p in enumerate(polys):
        if min(p) >= min(vs):
            is_sock[i] = True
print('[G] socket polys', sum(1 for x in is_sock if x), 'of', len(polys), flush=True)


def build(include_socket, V):
    tris, own = [], []
    for i, p in enumerate(polys):
        if is_sock[i] and not include_socket:
            continue
        for k in range(1, len(p) - 1):
            tris.append((p[0], p[k], p[k + 1])); own.append(i)
    bvh = BVHTree.FromPolygons([tuple(x) for x in V], tris, all_triangles=True)
    return bvh, own


cam_d = bpy.data.cameras.new('CAM'); cam_d.type = 'ORTHO'
cam = bpy.data.objects.new('CAM', cam_d); sc.collection.objects.link(cam); sc.camera = cam
res = {'tag': TAG, 'blend': BLD, 'keys': {}}
N = 320
for key in ('L_hip', 'R_hip'):
    c = cams[key]
    res['keys'][key] = {}
    for bend in (0.0, 60.0, 90.0):
        J.clear_pose(arm)
        J.set_rot(arm, INFO[key][0], np.array(c['a1']), bend)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        obe = body.evaluated_get(dg)
        m2 = obe.to_mesh()
        MW2 = np.array(body.matrix_world)
        V2 = np.array([list(v.co) for v in m2.vertices], dtype=np.float64) @ MW2[:3, :3].T + MW2[:3, 3]
        obe.to_mesh_clear()
        bvhA, ownA = build(True, V2)
        bvhB, ownB = build(False, V2)
        res['keys'][key]['bend%d' % int(bend)] = {}
        for suf in ('front', 'side'):
            cam_d.ortho_scale = c['scale_' + suf]
            cam.location = Vector(c['J']) + Vector(c[suf]).normalized() * 6.0
            cam.rotation_euler = (Vector(c['J']) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
            bpy.context.view_layer.update()
            o_dir = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
            st = dict(sock_visible=0, bg_with=0, bg_without=0, opened=0, total=0)
            for py in range(N):
                for px in range(N):
                    nx = (px + 0.5) / N; ny = (py + 0.5) / N
                    o = cam.matrix_world @ Vector(((nx - 0.5) * cam_d.ortho_scale, (ny - 0.5) * cam_d.ortho_scale, 0.0))
                    o = o - o_dir * 6.0
                    ha = bvhA.ray_cast(o, o_dir, 12.0)
                    hb = bvhB.ray_cast(o, o_dir, 12.0)
                    st['total'] += 1
                    if ha[0] is not None and is_sock[ownA[ha[2]]]:
                        st['sock_visible'] += 1
                    if ha[0] is None:
                        st['bg_with'] += 1
                    if hb[0] is None:
                        st['bg_without'] += 1
                        if ha[0] is not None and is_sock[ownA[ha[2]]]:
                            st['opened'] += 1
            for k in st:
                st[k] = int(st[k])
            st['px_equiv'] = 'x%.1f of %dx%d grid' % (1.0, N, N)
            res['keys'][key]['bend%d' % int(bend)][suf] = st
            print('[G] %s %-6s %-5s socket_px=%d  bg_with=%d bg_without=%d  (rays %d)'
                  % (key, 'bend%d' % int(bend), suf, st['sock_visible'], st['bg_with'], st['bg_without'], st['total']), flush=True)
J.clear_pose(arm)
json.dump(res, open(OUT, 'w'), indent=1)
print('[G] DONE', OUT, flush=True)
