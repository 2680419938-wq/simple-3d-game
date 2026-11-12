# softskin.py -- soften rigid weights on skin/fur geometry (armor & claws stay rigid)
import bpy, sys, os, json, math
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:]
O = {}
i = 0
while i < len(a):
    if a[i].startswith('--'):
        k = a[i].lstrip('-'); v = a[i + 1] if i + 1 < len(a) and not a[i + 1].startswith('--') else '1'
        O[k] = v; i += 2 if (i + 1 < len(a) and not a[i + 1].startswith('--')) else 1
    else:
        i += 1

SRC = O['src']; OUTB = O['out-blend']; GLB = O.get('out-glb')
ALPHA = float(O.get('alpha', '0.55'))      # how much of the new distance-based weight to mix in
SIGMA = float(O.get('sigma', '0.05'))      # falloff in metres
MAXINF = 4
SOFT_MATS = {'DragonMan_Skin', 'DragonMan_Fur'}

bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
bones = [b for b in arm.data.bones]
bnames = [b.name for b in bones]
A_world = arm.matrix_world
segs = []
for b in bones:
    h = A_world @ b.head_local; t = A_world @ b.tail_local
    segs.append((np.array(h), np.array(t)))
log = {'alpha': ALPHA, 'sigma': SIGMA, 'meshes': {}}

def seg_dist(P, A, B):
    AB = B - A
    L2 = float(AB @ AB)
    if L2 < 1e-12:
        return np.linalg.norm(P - A, axis=1)
    t = np.clip(((P - A) @ AB) / L2, 0.0, 1.0)[:, None]
    proj = A + t * AB
    return np.linalg.norm(P - proj, axis=1)

for ob in bpy.data.objects:
    if ob.type != 'MESH' or ob.name.startswith('WGT_'):
        continue
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64); me.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    M = np.array(ob.matrix_world)
    P = co @ M[:3, :3].T + M[:3, 3]

    # per-vertex material (majority of incident faces)
    vmat = np.full(n, -1, dtype=np.int32)
    counts = {}
    for poly in me.polygons:
        mi = poly.material_index
        for vi in poly.vertices:
            counts.setdefault(vi, {})
            counts[vi][mi] = counts[vi].get(mi, 0) + 1
    for vi, d in counts.items():
        vmat[vi] = max(d.items(), key=lambda kv: kv[1])[0]
    mat_names = [m.name if m else '' for m in me.materials]
    soft_mask = np.array([mat_names[vmat[i]] in SOFT_MATS if vmat[i] >= 0 and vmat[i] < len(mat_names) else False for i in range(n)])

    # current weights
    gidx = {g.name: g.index for g in ob.vertex_groups}
    W = np.zeros((n, len(bnames)), dtype=np.float64)
    for v in me.vertices:
        for g in v.groups:
            nm = ob.vertex_groups[g.group].name
            j = bnames.index(nm) if nm in bnames else -1
            if j >= 0:
                W[v.index, j] = g.weight

    D = np.empty((n, len(bnames)), dtype=np.float64)
    for j, (hh, tt) in enumerate(segs):
        D[:, j] = seg_dist(P, hh, tt)
    # allow only bones reasonably near the nearest one
    dmin = D.min(axis=1, keepdims=True)
    gate = D <= np.maximum(dmin * 3.0, dmin + 0.12)
    Dw = np.exp(-((D / SIGMA) ** 2)) * gate

    Wn = W / np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
    Dn = Dw / np.maximum(Dw.sum(axis=1, keepdims=True), 1e-9)
    blend = ALPHA * Dn + (1.0 - ALPHA) * Wn
    newW = np.where(soft_mask[:, None], blend, Wn)

    # keep top-4 and renormalise
    order = np.argsort(-newW, axis=1)
    keep = np.zeros_like(newW, dtype=bool)
    rows = np.arange(n)[:, None]
    keep[rows, order[:, :MAXINF]] = True
    newW = np.where(keep, newW, 0.0)
    newW = newW / np.maximum(newW.sum(axis=1, keepdims=True), 1e-9)
    # never drop the original dominant bone
    dom_old = np.argmax(Wn, axis=1)
    lost = 0
    for vi in range(n):
        j = dom_old[vi]
        if Wn[vi, j] > 0.5 and newW[vi, j] <= 0:
            lost += 1
    changed = 0
    for j, nm in enumerate(bnames):
        vg = ob.vertex_groups.get(nm) or ob.vertex_groups.new(name=nm)
        sel = np.where(newW[:, j] > 1e-5)[0]
        if len(sel) == 0:
            continue
        for vi in sel:
            old = W[vi, j]
            nw = float(newW[vi, j])
            if abs(nw - old) > 1e-4:
                vg.add([int(vi)], nw, 'REPLACE')
                changed += 1
    log['meshes'][ob.name] = {'verts': n, 'soft_verts': int(soft_mask.sum()),
                              'changed_weight_entries': changed, 'lost_dominant': lost,
                              'inf_before': float((W > 1e-5).sum(axis=1).mean()),
                              'inf_after': float((newW > 1e-5).sum(axis=1).mean())}
    print('[SS]', ob.name, log['meshes'][ob.name])

bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[SS] saved', OUTB)
if GLB:
    COMMON = dict(export_format='GLB', use_selection=True, use_visible=False, export_apply=False,
        export_yup=True, export_texcoords=True, export_normals=True, export_tangents=False,
        export_materials='EXPORT', export_image_format='JPEG', export_image_quality=90,
        export_jpeg_quality=90, export_skins=True, export_def_bones=True, export_influence_nb=4,
        export_all_influences=False, export_rest_position_armature=True, export_leaf_bone=False,
        export_hierarchy_flatten_bones=False, export_anim_slide_to_zero=True, export_frame_range=False,
        export_optimize_animation_size=False, export_optimize_animation_keep_anim_armature=True,
        export_animation_mode='ACTIONS', export_anim_single_armature=True, export_force_sampling=True,
        export_morph=False, export_cameras=False, export_lights=False, export_extras=False)
    meshes = [bpy.data.objects[n] for n in ('DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R')]
    for o in bpy.data.objects: o.select_set(False)
    for o in meshes + [arm]: o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    for x in bpy.data.actions: x.use_fake_user = True
    kw = dict(COMMON); kw['export_animations'] = True
    bpy.ops.export_scene.gltf(filepath=GLB, **kw)
    print('[SS] exported', GLB, os.path.getsize(GLB))
if O.get('report'):
    json.dump(log, open(O['report'], 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
