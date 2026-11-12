# -*- coding: utf-8 -*-
# m11: cuff_check_rays_glb.py with a bone-name map, for the Mixamo-named merged rig.
# 24 rays per knee side, outside -> joint centre, all Walk frames; identical geometry/tolerances.
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
argv = sys.argv[sys.argv.index('--') + 1:]
GLB, OUT = argv[0], argv[1]
NANG = 24; RAD = 0.15
MAP = {'thigh.L': 'LeftUpLeg', 'thigh.R': 'RightUpLeg', 'shin.L': 'LeftLeg', 'shin.R': 'RightLeg'}
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.fps, sc.render.fps_base = 30, 1.0
bpy.ops.import_scene.gltf(filepath=GLB)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('DragonMan')]
if arm.animation_data is None: arm.animation_data_create()
arm.animation_data.action = bpy.data.actions['Walk']
def find(sub):
    for n in arm.pose.bones.keys():
        if n.lower() == sub.lower(): return n
    for n in arm.pose.bones.keys():
        if sub.lower() in n.lower(): return n
    for n in arm.pose.bones.keys():
        if MAP.get(sub, '@@@').lower() in n.lower(): return n
    raise KeyError(sub)
B = {k: find(k) for k in ('thigh.L', 'thigh.R', 'shin.L', 'shin.R')}
print('[RGLB] bones', B)
dg = bpy.context.evaluated_depsgraph_get()
tot = hit = 0; per = []; misses = []
nf = 33
for f in range(0, nf):
    sc.frame_set(0); sc.frame_set(f); dg.update()
    bvhs = []
    for ob in meshes:
        ev = ob.evaluated_get(dg); me = ev.to_mesh()
        MW = np.array(ev.matrix_world)
        co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        co = co @ MW[:3, :3].T + MW[:3, 3]
        polys = [tuple(p.vertices) for p in me.polygons]
        bvhs.append(BVHTree.FromPolygons([tuple(v) for v in co], polys, all_triangles=False))
        ev.to_mesh_clear()
    rec = {}
    for s in 'LR':
        J = np.array(arm.matrix_world @ arm.pose.bones[B['shin.' + s]].head)
        K = np.array(arm.matrix_world @ arm.pose.bones[B['thigh.' + s]].head)
        ax = (J - K); ax /= np.linalg.norm(ax)
        ex = np.cross(ax, np.array([0.0, 0, 1.0]))
        if np.linalg.norm(ex) < 1e-5: ex = np.array([1.0, 0, 0])
        ex /= np.linalg.norm(ex); ey = np.cross(ax, ex)
        h = 0; miss = []
        for i in range(NANG):
            a = 2 * math.pi * i / NANG
            d = math.cos(a) * ex + math.sin(a) * ey
            o = J + d * RAD; best = None
            for bvh in bvhs:
                loc, nor, idx, dist = bvh.ray_cast(Vector(o), Vector(-d), RAD)
                if loc is not None and (best is None or dist < best): best = dist
            if best is not None: h += 1
            else: miss.append(i)
        rec[s] = {'hits': h, 'miss': miss}
        tot += NANG; hit += h
        if miss: misses.append({'f': f + 1, 'side': s, 'ang': miss})
    per.append(rec)
print('[RGLB] %s  walk frames %d  ring rays %d/%d  hit_rate %.4f  100%%=%s  worst frame-side %d/%d'
      % (os.path.basename(GLB), nf, hit, tot, hit / tot, hit == tot,
         min(min(r['L']['hits'], r['R']['hits']) for r in per), NANG))
print('[RGLB] frames/sides with misses: %d %s' % (len(misses), misses[:8]))
json.dump({'glb': GLB, 'total': tot, 'hits': hit, 'rate': hit / tot, 'misses': misses, 'bones': B},
          open(OUT, 'w'), indent=1)
print('[RGLB] DONE')
