
# -*- coding: utf-8 -*-
"""hip_reshape: re-shape ONLY the two hip socket shells in place (same verts/faces/UV/weights),
so the rest pose stops showing the skin ball, while the shells still enclose J.

r(dir) = clamp(FAC * dist_skin(J,dir), ROPEN, CAP)   (open crotch dirs -> ROPEN dimple)
Usage:
  blender -b --python hip_reshape.py -- sweep '<json list of variants>' [outdir]
  blender -b --python hip_reshape.py -- apply '<json variant>' <outblend> [outdir]
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

JW = r'D:\ai\建模\dragon-men-rebuild\joint-work'
sys.path.insert(0, os.path.join(JW, 'scripts'))
import jlib as J

BLD = os.path.join(JW, 'DragonMan_Joint_full.blend')
BR = json.load(open(os.path.join(JW, 'verify', 'build_report.json'), encoding='utf-8'))
CAMS = json.load(open(os.path.join(JW, 'renders', 'cams.json'), encoding='utf-8'))
RP = json.load(open(os.path.join(JW, 'verify', 'rays_post.json'), encoding='utf-8'))['res']

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
MODE = ARGS[0]
SPEC = json.load(open(ARGS[1], encoding='utf-8')) if os.path.exists(ARGS[1]) else json.loads(ARGS[1])
OUTBLEND = ARGS[2] if MODE == 'apply' else None
OUTDIR = ARGS[3] if len(ARGS) > 3 else os.path.join(JW, 'renders', 'rework', 'exp')
os.makedirs(OUTDIR, exist_ok=True)
N0V = 21870
HIPS = ('L_hip', 'R_hip')
REC = {j['key']: j for j in BR['joints']}

bpy.ops.wm.open_mainfile(filepath=BLD)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
ACT = arm.animation_data.action if arm.animation_data else None
if ACT is not None:
    arm.animation_data.action = None
J.clear_pose(arm)
bpy.context.view_layer.update()
W0 = None
if 'World' in bpy.data.worlds and bpy.data.worlds['World'].use_nodes:
    _bg = bpy.data.worlds['World'].node_tree.nodes.get('Background')
    if _bg is not None:
        W0 = (tuple(_bg.inputs[0].default_value), float(_bg.inputs[1].default_value))
body = bpy.data.objects['DragonMan_Body']
me = body.data
MW = np.array(body.matrix_world)
MWi = Matrix(body.matrix_world).inverted()
co0 = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co0); co0 = co0.reshape(-1, 3)
PW = co0 @ MW[:3, :3].T + MW[:3, 3]
orig_faces = [tuple(p.vertices) for p in me.polygons if max(p.vertices) < N0V]
skin = BVHTree.FromPolygons([tuple(v) for v in PW], orig_faces, all_triangles=False)
objs = [bpy.data.objects[n] for n in J.MESHES]


def perp_basis(u):
    u = Vector(u)
    a = Vector((0, 0, 1))
    if abs(u.dot(a)) > 0.9:
        a = Vector((0, 1, 0))
    v = u.cross(a).normalized()
    w = u.cross(v).normalized()
    return np.array(v), np.array(w)


def dist_dir(Jw, d, rmax=0.6):
    h = skin.ray_cast(Vector(Jw), Vector(d), rmax)
    return None if h[0] is None else float(h[3])


# ---- precompute per-hip direction tables (independent of the variant) ----
INFO = {}
for key in HIPS:
    jd = REC[key]
    b, n = jd['base'], jd['nvp']
    Jc = np.array(jd['J'])
    u = np.array(jd['u']); u = u / np.linalg.norm(u)
    tw, sw = perp_basis(u)
    dirs = []          # 80 ring verts + top pole + bottom pole
    for k in range(1, 6):
        ph = math.pi * k / 6.0
        for i in range(16):
            a = 2 * math.pi * i / 16.0
            d = math.cos(ph) * u + math.sin(ph) * (math.cos(a) * tw + math.sin(a) * sw)
            dirs.append(d / np.linalg.norm(d))
    dirs.append(u.copy())
    dirs.append(-u.copy())
    assert len(dirs) == n, (key, len(dirs), n)
    ds = [dist_dir(Jc, d, 0.6) for d in dirs]
    INFO[key] = dict(base=b, n=n, J=Jc, u=u, dirs=dirs, ds=ds)
    print('[H] %s dirs %d open %d dmin %.5f dmed %.5f' % (
        key, n, sum(1 for x in ds if x is None),
        min([x for x in ds if x is not None] or [0]), float(np.median([x for x in ds if x is not None] or [0]))), flush=True)


def radii(key, FAC, CAP, ROPEN, SMOOTH):
    I = INFO[key]
    ds = I['ds']
    r = np.array([ROPEN if d is None else min(FAC * d, CAP) for d in ds])
    r = np.maximum(r, ROPEN)
    # smooth over the 5x16 ring grid (theta wraps), then across rows; poles untouched
    G = r[:80].reshape(5, 16).copy()
    for _ in range(SMOOTH):
        th = 0.5 * G + 0.25 * np.roll(G, 1, axis=1) + 0.25 * np.roll(G, -1, axis=1)
        row = th.copy()
        row[1:-1] = 0.5 * th[1:-1] + 0.25 * th[:-2] + 0.25 * th[2:]
        row[0] = 0.5 * th[0] + 0.5 * th[1]
        row[-1] = 0.5 * th[-1] + 0.5 * th[-2]
        G = row
    r[:80] = G.reshape(-1)
    # containment guard: never exceed 0.95 * skin distance
    for i, d in enumerate(I['ds']):
        if d is not None:
            r[i] = min(r[i], 0.95 * d)
    r = np.maximum(r, ROPEN * 0.5)
    return r


def apply_variant(v):
    for key in HIPS:
        I = INFO[key]
        r = radii(key, v['FAC'], v['CAP'], v['ROPEN'], v.get('SMOOTH', 1))
        for i in range(I['n']):
            p = I['J'] + r[i] * I['dirs'][i]
            q = MWi @ Vector((p[0], p[1], p[2], 1.0))
            me.vertices[I['base'] + i].co = (q[0], q[1], q[2])
    me.update()
    bpy.context.view_layer.update()


def restore():
    arr = co0.ravel()
    me.vertices.foreach_set('co', arr)
    me.update()
    bpy.context.view_layer.update()


# ---------- measurement ----------
def rest_visible(key, ndir=12):
    """orthographic coverage of the socket seen from ndir directions around J."""
    I = INFO[key]; b, n = I['base'], I['n']
    sf = [tuple(p.vertices) for p in me.polygons if all(b <= v < b + n for v in p.vertices)]
    of = [tuple(p.vertices) for p in me.polygons if not all(b <= v < b + n for v in p.vertices)]
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    W = co @ MW[:3, :3].T + MW[:3, 3]
    V = [tuple(x) for x in W]
    bs = BVHTree.FromPolygons(V, sf, all_triangles=False)
    bo = BVHTree.FromPolygons(V, of, all_triangles=False)
    tot = 0
    GA = math.pi * (3 - math.sqrt(5))
    for k in range(ndir):
        z = 1 - 2 * (k + 0.5) / ndir
        rr2 = math.sqrt(max(0.0, 1 - z * z)); th = GA * k
        d = np.array([rr2 * math.cos(th), rr2 * math.sin(th), z])
        ea = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0, 0])
        e1 = np.cross(d, ea); e1 /= np.linalg.norm(e1); e2 = np.cross(d, e1)
        N = 90; s = 0.14
        vis = 0
        for iy in range(N):
            y = (0.5 - (iy + 0.5) / N) * s
            for ix in range(N):
                x = ((ix + 0.5) / N - 0.5) * s
                o = I['J'] + e1 * x + e2 * y + d * 0.9
                hs = bs.ray_cast(Vector(o), Vector(-d), 1.2)
                if hs[0] is None:
                    continue
                ho = bo.ray_cast(Vector(o), Vector(-d), 1.2)
                if ho[0] is None or ho[3] > hs[3] + 1e-6:
                    vis += 1
        tot += vis
    return tot


def occlusion(key):
    I = INFO[key]
    cb = REC[key]['bone']
    Jw, Ct = J.bh(arm, cb)
    u = J.unit(Ct - Jw)
    a1 = J.flex_axis(u)
    rad_eff = float(RP[key]['rad'])
    out = {}
    for deg in (0, 30, 60, 90):
        J.set_rot(arm, cb, a1, float(deg))
        dgp = bpy.context.evaluated_depsgraph_get()
        bvh = J.obj_bvh(objs, dgp)
        Jp = np.array(arm.matrix_world @ arm.pose.bones[cb].head)
        dA = J.ring_dirs(a1, 24); dB = J.ring_dirs(u, 24)
        hA, _ = J.measure(bvh, Jp, dA, rad_eff)
        hB, _ = J.measure(bvh, Jp, dB, rad_eff)
        hA6, _ = J.measure(bvh, Jp, dA, 0.06)
        hB6, _ = J.measure(bvh, Jp, dB, 0.06)
        out['bend%d' % deg] = dict(eff=round((hA + hB) / 48.0, 4), r06=round((hA6 + hB6) / 48.0, 4))
    J.clear_pose(arm)
    bpy.context.view_layer.update()
    return out


# ---------- render rig (identical to j3_render) ----------
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


def render_rest(tag, keys=HIPS, views=('front', 'side')):
    for key in keys:
        c = CAMS[key]
        for suf in views:
            shoot('%s_%s_bend0_%s.png' % (tag, key, suf), c['J'], c[suf],
                  c['scale_front'] if suf == 'front' else c['scale_side'])


report = {}
variants = SPEC if MODE == 'sweep' else [SPEC]
for v in variants:
    tag = v.get('tag', 'v')
    restore()
    apply_variant(v)
    if MODE == 'apply':
        for nm in ('CAM', 'S0', 'S1'):
            ob = bpy.data.objects.get(nm)
            if ob is not None:
                bpy.data.objects.remove(ob, do_unlink=True)
        for coll, nm in ((bpy.data.lights, 'S0'), (bpy.data.lights, 'S1'), (bpy.data.cameras, 'CAM')):
            d = coll.get(nm)
            if d is not None:
                coll.remove(d)
        if W0 is not None:
            _bg = bpy.data.worlds['World'].node_tree.nodes.get('Background')
            _bg.inputs[0].default_value = W0[0]
            _bg.inputs[1].default_value = W0[1]
        me.update()
        if ACT is not None:
            if arm.animation_data is None:
                arm.animation_data_create()
            arm.animation_data.action = ACT
            try:
                arm.animation_data.action_slot = ACT.slots[0]
            except Exception as e:
                print('[H] slot warn', e)
            print('[H] action restored', ACT.name, ACT.users)
        bpy.ops.wm.save_as_mainfile(filepath=OUTBLEND)
        print('[H] saved', OUTBLEND, os.path.getsize(OUTBLEND))
    # geometry check
    geo = {}
    for key in HIPS:
        I = INFO[key]
        S = np.array([np.array((MW @ np.array([me.vertices[I['base'] + i].co.x,
                                                  me.vertices[I['base'] + i].co.y,
                                                  me.vertices[I['base'] + i].co.z, 1.0]))[:3]) for i in range(I['n'])])
        rr = np.linalg.norm(S - I['J'], axis=1)
        geo[key] = dict(rmin=round(float(rr.min()), 5), rmax=round(float(rr.max()), 5),
                        extent=[round(float(x), 4) for x in (S.max(0) - S.min(0))])
    vis = {k: rest_visible(k) for k in HIPS}
    occ = {k: occlusion(k) for k in HIPS}
    if MODE != 'apply':
        render_rest(tag)
    report[tag] = dict(v=v, geo=geo, vis_px=vis, occ=occ)
    print('[H] %-6s geo=%s vis=%s occ=%s' % (tag, json.dumps(geo), vis, json.dumps(occ)), flush=True)

restore()
json.dump(report, open(os.path.join(OUTDIR, '_sweep.json'), 'w'), indent=1)
print('[H] DONE', MODE)
