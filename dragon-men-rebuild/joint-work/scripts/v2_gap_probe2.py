# -*- coding: utf-8 -*-
"""v2_gap_probe2: where does the crotch actually leak? For each hip camera/view/bend:
cast the 320x320 ortho grid, split background into exterior (border-connected) and interior
(see-through gap), and for every interior pixel measure the closest approach of the ray to the
body surface (= the throat of the channel) and dump those throat points.
Usage: blender -b --factory-startup --python v2_gap_probe2.py -- <blend> <camjson> <out.json> <pngdir>
"""
import bpy, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import jlib as J

A = sys.argv[sys.argv.index('--') + 1:]
BLD, CAMJSON, OUT, PNGDIR = A[0], A[1], A[2], A[3]
os.makedirs(PNGDIR, exist_ok=True)
BR = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'verify', 'build_report.json'), encoding='utf-8'))
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
    return BVHTree.FromPolygons([tuple(x) for x in co], polys, all_triangles=False), co


cam_d = bpy.data.cameras.new('CAM'); cam_d.type = 'ORTHO'
cam = bpy.data.objects.new('CAM', cam_d); sc.collection.objects.link(cam); sc.camera = cam
res = {'blend': BLD, 'keys': {}}
for key in ('L_hip', 'R_hip'):
    c = cams[key]
    res['keys'][key] = {}
    cb = INFO[key][0]
    for bend in (0.0, 90.0):
        J.clear_pose(arm)
        J.set_rot(arm, INFO[key][0], np.array(c['a1']), bend)
        bpy.context.view_layer.update()
        bvh, co = body_bvh()
        res['keys'][key]['bend%d' % int(bend)] = {}
        for suf in ('front', 'side'):
            cam_d.ortho_scale = c['scale_' + suf]
            cam.location = Vector(c['J']) + Vector(c[suf]).normalized() * 6.0
            cam.rotation_euler = (Vector(c['J']) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
            bpy.context.view_layer.update()
            o_dir = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
            M = cam.matrix_world.copy()
            sc_ = cam_d.ortho_scale
            hit = np.zeros((N, N), dtype=bool)
            origins = np.zeros((N, N, 3))
            for py in range(N):
                for px in range(N):
                    nx = (px + 0.5) / N; ny = (py + 0.5) / N
                    o = M @ Vector(((nx - 0.5) * sc_, (ny - 0.5) * sc_, 0.0))
                    o = o - o_dir * 6.0
                    origins[py, px] = (o.x, o.y, o.z)
                    hit[py, px] = bvh.ray_cast(o, o_dir, 20.0)[0] is not None
            bg = ~hit
            # exterior = bg connected to image border
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
                        ext[yy, xx] = True
                        stack.append((yy, xx))
            gap = bg & ~ext
            ys, xs = np.nonzero(gap)
            # throat: closest approach of each gap ray to the surface
            tstat = []
            pts = []
            for y, x in zip(ys, xs):
                o = Vector(origins[y, x])
                best = None; bt = None
                for k in range(1, 121):
                    t = 0.01 * k
                    p = o + o_dir * t
                    loc, nor, idx, dd = bvh.find_nearest(p)
                    if loc is None:
                        continue
                    if best is None or dd < best:
                        best = dd; bt = t; bp = p
                if best is not None:
                    tstat.append(best)
                    pts.append((float(bp.x), float(bp.y), float(bp.z), float(best), float(bt)))
            tstat = np.array(tstat) if tstat else np.array([0.0])
            res['keys'][key]['bend%d' % int(bend)][suf] = dict(
                n_gap=int(gap.sum()), n_bg=int(bg.sum()), n_hit=int(hit.sum()),
                gap_frac=round(float(gap.sum()) / (N * N), 5),
                throat_p10=round(float(np.percentile(tstat, 10)), 4),
                throat_med=round(float(np.median(tstat)), 4),
                throat_p90=round(float(np.percentile(tstat, 90)), 4),
                throat_max=round(float(tstat.max()), 4))
            print('[Q] %-6s bend%-3d %-5s gap=%4d (%.3f%%) bg=%6d  throat d p10/med/p90 %s = %.4f %.4f %.4f' % (
                key, int(bend), suf, gap.sum(), 100.0 * gap.sum() / (N * N), bg.sum(),
                '', np.percentile(tstat, 10), np.median(tstat), np.percentile(tstat, 90)), flush=True)
            np.save(os.path.join(PNGDIR, 'gapmask_%s_bend%d_%s.npy' % (key, int(bend), suf)), gap)
            with open(os.path.join(PNGDIR, 'throat_%s_bend%d_%s.json' % (key, int(bend), suf)), 'w') as f:
                json.dump(pts, f)
            # visual mask png via blender image
            img = bpy.data.images.new('m', N, N, alpha=False)
            px = np.zeros((N, N, 4), dtype=np.float32)
            px[..., 0] = gap.astype(np.float32)
            px[..., 1] = hit.astype(np.float32) * 0.25
            px[..., 3] = 1.0
            img.pixels.foreach_set(px.ravel())
            img.filepath_raw = os.path.join(PNGDIR, 'gapmask_%s_bend%d_%s.png' % (key, int(bend), suf))
            img.file_format = 'PNG'
            img.save()
J.clear_pose(arm)
json.dump(res, open(OUT, 'w'), indent=1)
print('[Q] DONE', OUT, flush=True)
