# -*- coding: utf-8 -*-
"""TASK2 diagnosis: is the L_elbow bend90 diagonal streak a UV-copy (texture) artifact or a
shading/normal one? Renders the same camera in three material regimes and reports numeric
UV-area vs 3D-area ratios plus a camera ray classification of the visible surface.
Usage: blender -b --factory-startup --python elbow_diag.py -- <blend> <camjson> <outdir>
"""
import bpy, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import jlib as J

A = sys.argv[sys.argv.index('--') + 1:]
BLD, CAMJSON, OUTDIR = A[0], A[1], A[2]
KEY = 'L_elbow'
os.makedirs(OUTDIR, exist_ok=True)
INFO = {k: (cb, pb) for k, cb, pb, tw in J.JOINTS}

bpy.ops.wm.open_mainfile(filepath=BLD)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
if arm.animation_data:
    arm.animation_data.action = None
J.clear_pose(arm)
cams = json.load(open(CAMJSON))
c = cams[KEY]
cb, pb = INFO[KEY]
J.set_rot(arm, cb, np.array(c['a1']), 90.0)
bpy.context.view_layer.update()

sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 24
sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 640
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'Standard'
cam_d = bpy.data.cameras.new('CAM'); cam_d.type = 'ORTHO'
cam_d.ortho_scale = c['scale_front']
cam = bpy.data.objects.new('CAM', cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam.location = Vector(c['J']) + Vector(c['front']).normalized() * 6.0
cam.rotation_euler = (Vector(c['J']) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
for i, e in enumerate((7.0, 3.5)):
    sd = bpy.data.lights.new('S%d' % i, 'SUN'); sd.energy = e; sd.angle = math.radians(12)
    so = bpy.data.objects.new('S%d' % i, sd); sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(52), 0, math.radians(35 + 100 * i))
w = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.05, 0.055, 0.07, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 0.55
bpy.context.view_layer.update()


def mat_white():
    m = bpy.data.materials.new('OVR_WHITE'); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.75, 0.72, 0.70, 1)
    b.inputs['Roughness'].default_value = 0.55
    return m


def mat_check(n=512, cell=32):
    img = bpy.data.images.new('CHK', n, n, alpha=False)
    px = np.zeros((n, n, 4), dtype=np.float32); px[..., 3] = 1.0
    xs = np.arange(n); ys = np.arange(n)
    gx = (xs // cell) % 2; gy = (ys // cell) % 2
    chk = np.logical_xor(gx[None, :], gy[:, None])
    px[..., 0] = np.where(chk, 0.95, 0.18)
    px[..., 1] = np.where(chk, 0.35, 0.55)
    px[..., 2] = np.where(chk, 0.20, 0.85)
    line = ((xs % cell) < 2)[None, :] | ((ys % cell) < 2)[:, None]
    for k in range(3):
        px[..., k] = np.where(line, 0.02, px[..., k])
    img.pixels = px.ravel().tolist()
    img.pack()
    m = bpy.data.materials.new('OVR_CHK'); m.use_nodes = True
    nt = m.node_tree
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; tex.interpolation = 'Closest'
    b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.75
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    return m


def shoot(name, override):
    bpy.context.view_layer.material_override = override
    sc.render.filepath = os.path.join(OUTDIR, name)
    bpy.ops.render.render(write_still=True)
    print('[D] render', name, 'override', override.name if override else None, flush=True)


shoot('_e1_normal.png', None)
shoot('_e1_flat.png', mat_white())
shoot('_e1_check.png', mat_check())
bpy.context.view_layer.material_override = None

# ---- numeric: UV density + visible-surface classification
body = bpy.data.objects['DragonMan_Body']
dg = bpy.context.evaluated_depsgraph_get()
obe = body.evaluated_get(dg)
me = obe.to_mesh()
MW = body.matrix_world
V = np.array([list(MW @ v.co) for v in me.vertices], dtype=np.float64)
polys = [tuple(p.vertices) for p in me.polygons]
matnames = [m.name if m else '?' for m in me.materials]
N0V = 21870
newp = [i for i, p in enumerate(polys) if min(p) >= N0V]
print('[D] polys %d new %d  uv layers %s' % (len(polys), len(newp), [l.name for l in me.uv_layers]), flush=True)


def areas(layer_name):
    lay = me.uv_layers[layer_name]
    uvs = np.array([list(d.uv) for d in lay.data], dtype=np.float64).reshape(-1, 2)
    a3 = np.zeros(len(polys)); au = np.zeros(len(polys))
    for i, p in enumerate(polys):
        if len(p) < 3:
            continue
        P = V[list(p)]
        ar = 0.0
        for k in range(1, len(p) - 1):
            ar += 0.5 * np.linalg.norm(np.cross(P[k] - P[0], P[k + 1] - P[0]))
        a3[i] = ar
        T = np.zeros((len(p), 2))
        for k, vi in enumerate(p):
            T[k] = uvs[me.loops[me.polygons[i].loop_start + k].index]
        auv = 0.0
        for k in range(1, len(p) - 1):
            auv += 0.5 * abs((T[k][0] - T[0][0]) * (T[k + 1][1] - T[0][1]) - (T[k + 1][0] - T[0][0]) * (T[k][1] - T[0][1]))
        au[i] = auv
    return a3, au


for lname in [l.name for l in me.uv_layers]:
    a3, au = areas(lname)
    sel = [i for i in newp if a3[i] > 1e-12]
    ratio = np.array([au[i] / a3[i] for i in sel])
    oth = [i for i in range(len(polys)) if i not in set(newp) and a3[i] > 1e-12]
    r_o = np.array([au[i] / a3[i] for i in oth])
    far = int((ratio > 3 * np.median(ratio)).sum())
    print('[D] %-12s UVdensity new: med %.1f p5 %.1f p95 %.1f max %.1f | orig med %.1f | new>3xmed %d/%d'
          % (lname, np.median(ratio), np.percentile(ratio, 5), np.percentile(ratio, 95), ratio.max(),
             np.median(r_o), far, len(sel)), flush=True)

# visible surface by camera rays
tris, owner = [], []
for i, p in enumerate(polys):
    for k in range(1, len(p) - 1):
        tris.append((p[0], p[k], p[k + 1])); owner.append(i)
bvh = BVHTree.FromPolygons([tuple(x) for x in V], tris, all_triangles=True)
inv = cam.matrix_world.inverted()
hitc = {}
nres = 160
o_dir = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
for py in range(nres):
    for px in range(nres):
        nx = (px + 0.5) / nres; ny = (py + 0.5) / nres
        loc = cam.matrix_world @ Vector(((nx - 0.5) * cam_d.ortho_scale, (ny - 0.5) * cam_d.ortho_scale, 0.0))
        loc = loc - o_dir * 6.0
        h = bvh.ray_cast(loc, o_dir, 12.0)
        if h[0] is None:
            continue
        pi = owner[h[2]]
        e = hitc.setdefault(pi, [0, 0.0])
        e[0] += 1
        d = np.linalg.norm(np.array(h[0]) - np.array(c['J']))
        e[1] = max(e[1], 0.0)
tot = sum(v[0] for v in hitc.values())
nw = sum(v[0] for pi, v in hitc.items() if pi in set(newp))
print('[D] visible rays %d  on new faces %d (%.1f%%)' % (tot, nw, 100.0 * nw / max(1, tot)), flush=True)
top = sorted(hitc.items(), key=lambda kv: -kv[1][0])[:12]
a3c, auc = areas(me.uv_layers[0].name)
for pi, (cnt, _) in top:
    p = polys[pi]
    cen = V[list(p)].mean(axis=0)
    dd = np.linalg.norm(cen - np.array(c['J']))
    print('[D]   poly %6d %s %-16s px %4d  r_from_J %.4f  uvdens %.1f'
          % (pi, 'NEW' if pi in set(newp) else 'org', matnames[me.polygons[pi].material_index],
             cnt, dd, auc[pi] / max(1e-12, a3c[pi])), flush=True)
obe.to_mesh_clear()
print('[D] DONE', flush=True)
