# -*- coding: utf-8 -*-
"""v2_throat2: proper closest-approach (ICP style) of every see-through ray, then statistics of
the throat point cloud per view: centroid, PCA axes/extents, channel half-width distribution.
Usage: blender -b --factory-startup --python v2_throat2.py -- <blend> <camjson> <out.json>
"""
import bpy, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import jlib as J

A = sys.argv[sys.argv.index('--') + 1:]
BLD, CAMJSON, OUT = A[0], A[1], A[2]
cams = json.load(open(CAMJSON))
INFO = {k: (cb, pb) for k, cb, pb, tw in J.JOINTS}
N = 320
bpy.ops.wm.open_mainfile(filepath=BLD)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data.action = None
J.clear_pose(arm)
body = bpy.data.objects['DragonMan_Body']


def body_bvh():
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    MW = np.array(body.matrix_world)
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons([tuple(x) for x in co], polys, all_triangles=False)


cam_d = bpy.data.cameras.new('CAM'); cam_d.type = 'ORTHO'
cam = bpy.data.objects.new('CAM', cam_d); sc.collection.objects.link(cam); sc.camera = cam
res = {}
allpts = {}
for key in ('L_hip', 'R_hip'):
    c = cams[key]
    for bend in (0.0, 90.0):
        J.clear_pose(arm)
        J.set_rot(arm, INFO[key][0], np.array(c['a1']), bend)
        bpy.context.view_layer.update()
        bvh = body_bvh()
        for suf in ('front', 'side'):
            cam_d.ortho_scale = c['scale_' + suf]
            cam.location = Vector(c['J']) + Vector(c[suf]).normalized() * 6.0
            cam.rotation_euler = (Vector(c['J']) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
            bpy.context.view_layer.update()
            o_dir = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
            M = cam.matrix_world.copy(); sc_ = cam_d.ortho_scale
            hit = np.zeros((N, N), dtype=bool); origins = np.zeros((N, N, 3))
            for py in range(N):
                for px in range(N):
                    nx = (px + 0.5) / N; ny = (py + 0.5) / N
                    o = M @ Vector(((nx - 0.5) * sc_, (ny - 0.5) * sc_, 0.0))
                    o = o - o_dir * 6.0
                    origins[py, px] = (o.x, o.y, o.z)
                    hit[py, px] = bvh.ray_cast(o, o_dir, 20.0)[0] is not None
            bg = ~hit
            ext = np.zeros_like(bg)
            st = [(0, x) for x in range(N)] + [(N - 1, x) for x in range(N)] + [(y, 0) for y in range(N)] + [(y, N - 1) for y in range(N)]
            for y, x in st:
                if bg[y, x] and not ext[y, x]:
                    ext[y, x] = True
            stack = [p for p in st if bg[p]]
            while stack:
                y, x = stack.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < N and 0 <= xx < N and bg[yy, xx] and not ext[yy, xx]:
                        ext[yy, xx] = True; stack.append((yy, xx))
            gap = bg & ~ext
            ys, xs = np.nonzero(gap)
            pts = []; ds = []
            for y, x in zip(ys, xs):
                o = Vector(origins[y, x]); t = 6.0
                best = (1e9, None)
                for _ in range(10):
                    p = o + o_dir * t
                    loc, nor, idx, dd = bvh.find_nearest(p)
                    if loc is None:
                        break
                    if dd < best[0]:
                        best = (dd, p.copy())
                    tn = (Vector(loc) - o).dot(o_dir)
                    if abs(tn - t) < 1e-4:
                        break
                    t = tn
                if best[1] is not None:
                    pts.append((best[1].x, best[1].y, best[1].z, best[0]))
                    ds.append(best[0])
            P = np.array([p[:3] for p in pts]) if pts else np.zeros((0, 3))
            tag = '%s_bend%d_%s' % (key, int(bend), suf)
            if len(P) > 8:
                cen = P.mean(0)
                X = P - cen
                C = X.T @ X / len(P)
                w, V = np.linalg.eigh(C)
                order = np.argsort(-w)
                ax = V[:, order]
                ext = [float(np.abs(X @ ax[:, i]).max() * 2) for i in range(3)]
                res[tag] = dict(n=int(len(P)), gap_px=int(gap.sum()),
                                center=[round(float(v), 4) for v in cen],
                                axes=[[round(float(v), 3) for v in ax[:, i]] for i in range(3)],
                                ext=[round(v, 4) for v in ext],
                                halfwidth_p10=round(float(np.percentile(ds, 10)), 4),
                                halfwidth_med=round(float(np.median(ds)), 4),
                                halfwidth_p90=round(float(np.percentile(ds, 90)), 4),
                                bbox_min=[round(float(v), 4) for v in P.min(0)],
                                bbox_max=[round(float(v), 4) for v in P.max(0)])
                allpts[tag] = [round(float(v), 4) for v in cen]
                print('[T] %-22s gap=%4d thr=%4d c=%s ext=%s hw p10/med/p90=%.4f/%.4f/%.4f' % (
                    tag, gap.sum(), len(P), np.round(cen, 3), res[tag]['ext'],
                    res[tag]['halfwidth_p10'], res[tag]['halfwidth_med'], res[tag]['halfwidth_p90']), flush=True)
                print('      axes', [res[tag]['axes'][i] for i in range(3)], flush=True)
            else:
                res[tag] = dict(n=int(len(P)), gap_px=int(gap.sum()))
                print('[T] %-22s gap=%4d thr=%4d (none)' % (tag, gap.sum(), len(P)), flush=True)
J.clear_pose(arm)
json.dump(res, open(OUT, 'w'), indent=1)
print('[T] DONE', flush=True)
