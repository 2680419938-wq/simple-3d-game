# -*- coding: utf-8 -*-
"""Final export: v2 neutral T-Pose blend -> 4 deliverable GLBs (LOD0/LOD1/LOD2 + TPose).

Run:  blender.exe -b --factory-startup -P _final_build.py
Writes only to  ...\dragon-men-rebuild\final\   and   ...\.dsh\tmp-final\
"""
import bpy, json, math, os, hashlib, time
from mathutils import Matrix, Vector

BLEND  = r'D:\ai\建模\dragon-men-rebuild\tpose-work-v2\DragonMan_Neutral_Tpose_v2.blend'
OUTDIR = r'D:\ai\建模\dragon-men-rebuild\final'
WORK   = r'D:\ai\建模\.dsh\tmp-final'
REPORT = os.path.join(WORK, '_final_build_report.json')

KEEP = ['root','pelvis','spine','chest','neck','head',
        'shoulder.L','upper_arm.L','forearm.L','hand.L',
        'shoulder.R','upper_arm.R','forearm.R','hand.R',
        'tail.001','tail.002','tail.003','tail.004','tail.005','tail.006',
        'thigh.L','shin.L','foot.L','toe.01.L','toe.02.L','toe.03.L',
        'thigh.R','shin.R','foot.R','toe.01.R','toe.02.R','toe.03.R']
assert len(KEEP) == 32 and len(set(KEEP)) == 32

#  tag, file, target tris, seed ratio, tex(other), tex(normal), animations
LODS = [('LOD0', 'DragonMan_Game.glb',      53012, None,  2048, 1024, True),
        ('TPOSE','DragonMan_TPose.glb',     None,  None,  2048, 1024, False),
        ('LOD1', 'DragonMan_Game_LOD1.glb', 26500, 0.500, 1024, 1024, True),
        ('LOD2', 'DragonMan_Game_LOD2.glb', 11650, 0.220,  512,  512, True)]

R = {}
def log(*a): print('[BUILD]', *a, flush=True)
def mdiff(m1, m2): return max(abs(a-b) for r1, r2 in zip(m1, m2) for a, b in zip(r1, r2))
def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for c in iter(lambda: fh.read(1 << 20), b''): h.update(c)
    return h.hexdigest().upper()
def tris(ob):
    ob.data.calc_loop_triangles(); return len(ob.data.loop_triangles)

t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
sc.render.fps, sc.render.fps_base = 30, 1.0
sc.frame_start, sc.frame_end = 1, 121
R['source_blend'] = BLEND
R['source_sha256'] = sha256(BLEND)
R['fps'] = sc.render.fps

arm = bpy.data.objects['DragonMan_Rig']
meshes = [bpy.data.objects[n] for n in ['DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R']]
R['bones_before'] = len(arm.data.bones)
R['deform_before'] = sum(1 for b in arm.data.bones if b.use_deform)
R['tris_before'] = [tris(o) for o in meshes]
assert R['bones_before'] == 78 and R['tris_before'] == [40348, 6332, 6332], R['tris_before']

# ---- 1 widgets out
R['widgets_removed'] = []
for n in ('WGT_pole', 'WGT_ring', 'WGT_root'):
    ob = bpy.data.objects.get(n)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True); R['widgets_removed'].append(n)

# ---- 2 join + flatten (bake object matrices into data)
bpy.ops.object.select_all(action='DESELECT')
for ob in meshes: ob.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()
mob = meshes[0]
Rm = mob.matrix_world.copy(); Ram = arm.matrix_world.copy()
for ob, M0 in ((mob, Rm), (arm, Ram)):
    ob.parent = None
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    ob.data.transform(M0)
bpy.context.view_layer.update()
R['materials'] = [m.name for m in mob.data.materials]
R['uv_layers'] = [l.name for l in mob.data.uv_layers]
R['verts_joined'] = len(mob.data.vertices)
R['polys_joined'] = len(mob.data.polygons)
R['tris_joined'] = tris(mob)
R['mesh_world_identity'] = (mob.matrix_world == Matrix.Identity(4))
R['arm_world_identity'] = (arm.matrix_world == Matrix.Identity(4))
assert R['tris_joined'] == 53012, R['tris_joined']
assert len(R['materials']) == 4, R['materials']
V = [v.co for v in mob.data.vertices]
R['bbox_after_flatten'] = [round(f([v.x for v in V]), 5) for f in (min, max)] + \
                          [round(f([v.y for v in V]), 5) for f in (min, max)] + \
                          [round(f([v.z for v in V]), 5) for f in (min, max)]
log('join ok', R['tris_joined'], R['materials'], R['bbox_after_flatten'])

# ---- 3 capture 121 frames of pose matrices for the 32 kept bones
arm.data.pose_position = 'POSE'
rec = []
for f in range(1, 122):
    sc.frame_set(f); bpy.context.view_layer.update()
    rec.append({n: arm.pose.bones[n].matrix.copy() for n in KEEP})
R['captured_frames'] = len(rec)

# ---- 4 weights: merge removed-bone groups into nearest kept ancestor, cap 4, normalise
parents = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
def kept_anc(nm):
    p = parents.get(nm); s = 0
    while p and p not in KEEP:
        p = parents.get(p); s += 1
        if s > 64: return None
    return p
merge_map = {}
for b in arm.data.bones:
    if b.name not in KEEP:
        t = kept_anc(b.name); assert t in KEEP, (b.name, t)
        merge_map[b.name] = t
R['merge_map'] = merge_map
R['removed_groups'] = len(merge_map)
gnames = [vg.name for vg in mob.vertex_groups]
assert not [n for n in gnames if n not in KEEP and n not in merge_map], 'stray group'

def rebuild_weights(ob):
    gn = [vg.name for vg in ob.vertex_groups]
    newW = []; st = {'max_inf': 0, 'zero': 0, 'sum_min': 9.0, 'sum_max': 0.0}
    for v in ob.data.vertices:
        d = {}
        for g in v.groups:
            if g.weight <= 0.0: continue
            nm = gn[g.group]
            tgt = nm if nm in KEEP else merge_map[nm]
            d[tgt] = d.get(tgt, 0.0) + g.weight
        if not d:
            d = {'pelvis': 1.0}; st['zero'] += 1
        items = sorted(d.items(), key=lambda kv: -kv[1])[:4]
        tot = sum(w for _, w in items)
        items = [(k, w / tot) for k, w in items]
        newW.append(items)
        st['max_inf'] = max(st['max_inf'], len(items))
        s = sum(w for _, w in items)
        st['sum_min'] = min(st['sum_min'], s); st['sum_max'] = max(st['sum_max'], s)
    ob.vertex_groups.clear()
    vgs = {n: ob.vertex_groups.new(name=n) for n in KEEP}
    for i, ws in enumerate(newW):
        for nm, w in ws: vgs[nm].add([i], w, 'REPLACE')
    return st

R['weight_stats_LOD0'] = rebuild_weights(mob)
R['vgroups_after'] = len(mob.vertex_groups)
used = set()
for v in mob.data.vertices:
    for g in v.groups: used.add(mob.vertex_groups[g.group].name)
R['nonempty_groups'] = sorted(used)

# ---- 5 delete bones + constraints
bpy.context.view_layer.objects.active = arm
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
for b in eb: b.use_connect = False
pre = {n: (eb[n].head.copy(), eb[n].tail.copy()) for n in KEEP}
for n in [b.name for b in eb if b.name not in KEEP]: eb.remove(eb[n])
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()
R['bones_after'] = len(arm.data.bones)
names_after = [b.name for b in arm.data.bones]
assert set(names_after) == set(KEEP), set(names_after) ^ set(KEEP)
R['bone_names'] = names_after
drift = max(max((arm.data.bones[n].head_local - pre[n][0]).length,
                (arm.data.bones[n].tail_local - pre[n][1]).length) for n in KEEP)
R['rest_drift_after_delete'] = float('%.3e' % drift)
assert drift < 1e-6, drift
ncon = 0
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        pb.constraints.remove(c); ncon += 1
R['constraints_removed'] = ncon
log('bones', R['bones_after'], 'drift', R['rest_drift_after_delete'], 'constraints removed', ncon)

# ---- 6 rebake Idle_Lively for the 32-bone rig
for n in KEEP: arm.pose.bones[n].rotation_mode = 'QUATERNION'
old = bpy.data.actions.get('Idle_Lively')
arm.animation_data.action = None
act = bpy.data.actions.new('Idle_Lively')
arm.animation_data.action = act
basel = {n: arm.data.bones[n].matrix_local.copy() for n in KEEP}
for fi, f in enumerate(range(1, 122)):
    snap = rec[fi]
    for n in KEEP:
        b = arm.data.bones[n]; pb = arm.pose.bones[n]; tgt = snap[n]
        if b.parent:
            rel = basel[b.parent.name].inverted() @ basel[n]
            pb.matrix_basis = rel.inverted() @ (snap[b.parent.name].inverted() @ tgt)
        else:
            pb.matrix_basis = basel[n].inverted() @ tgt
        pb.keyframe_insert('location', frame=f, group=n)
        pb.keyframe_insert('rotation_quaternion', frame=f, group=n)
        pb.keyframe_insert('scale', frame=f, group=n)
R['action_curves'] = sum(len(bag.fcurves) for layer in act.layers
                         for strip in layer.strips for bag in getattr(strip, 'channelbags', []))
if old: bpy.data.actions.remove(old)
act.name = 'Idle_Lively'
R['action_name'] = act.name
R['action_range'] = [round(x, 3) for x in act.frame_range]
err = 0.0
for fi, f in enumerate(range(1, 122)):
    sc.frame_set(f); bpy.context.view_layer.update()
    for n in KEEP: err = max(err, mdiff(arm.pose.bones[n].matrix, rec[fi][n]))
R['bake_max_err'] = float('%.3e' % err)
assert err < 1e-5, err
assert R['action_curves'] > 0
log('bake ok', R['action_curves'], 'curves, max err', R['bake_max_err'])

# ---- 7 build LOD meshes (COLLAPSE decimate; UV + skin weights preserved)
def make_lod(src, name, target, base_ratio):
    ratio = base_ratio; tries = []
    for _it in range(7):
        ob = src.copy(); ob.data = src.data.copy()
        ob.name = name; ob.data.name = name
        bpy.context.collection.objects.link(ob)
        for m in list(ob.modifiers):
            if m.type == 'ARMATURE': ob.modifiers.remove(m)
        md = ob.modifiers.new('DEC', 'DECIMATE')
        md.decimate_type = 'COLLAPSE'; md.ratio = ratio
        md.use_collapse_triangulate = True
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True); bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=md.name)
        n = tris(ob); tries.append([round(ratio, 5), n])
        if abs(n - target) <= 150:
            return ob, tries, n
        bpy.data.objects.remove(ob, do_unlink=True)
        ratio = max(0.01, min(0.999, ratio * float(target) / float(n)))
    raise RuntimeError('decimate did not converge: %s' % tries)

lod_objs = {}
R['decimate'] = {}
for tag, fname, target, ratio, _o, _n, _a in LODS:
    if ratio is None: continue
    ob, tries, n = make_lod(mob, tag, target, ratio)
    lod_objs[tag] = ob
    R['decimate'][tag] = {'target': target, 'achieved': n, 'tries': tries}
    log('decimate', tag, tries, '->', n)

def pick(tag):
    return mob if tag in ('LOD0', 'TPOSE') else lod_objs[tag]

# ---- 8 strict pivot: ankle midpoint -> blender (x=0, y=0) == glTF (x=0, z=0); sole -> z=0
all_meshes = [mob, lod_objs['LOD1'], lod_objs['LOD2']]
ank = (arm.data.bones['foot.L'].head_local + arm.data.bones['foot.R'].head_local) / 2.0
minz = min(min(v.co.z for v in o.data.vertices) for o in all_meshes)
# exact Rz(90deg) (Matrix.Rotation keeps cos(pi/2)~4.4e-8 in float32, which would
# leave a ~2e-8 residual on the ankle midpoint)
Rz = Matrix(((0.0, -1.0, 0.0, 0.0),
             (1.0,  0.0, 0.0, 0.0),
             (0.0,  0.0, 1.0, 0.0),
             (0.0,  0.0, 0.0, 1.0)))
t = Vector((ank.y, -ank.x, -minz))
M = Matrix.Translation(t) @ Rz
chk = M @ ank
R['pivot'] = {'ankle_mid_before': [round(x, 6) for x in ank],
              'min_z_all_meshes': round(minz, 6),
              'translation': [round(x, 6) for x in t],
              'ankle_mid_after_M': [round(x, 9) for x in chk],
              'residual_xy': float('%.3e' % max(abs(chk.x), abs(chk.y)))}
assert max(abs(chk.x), abs(chk.y)) < 1e-9, chk
for ob in all_meshes:
    ob.data.transform(M)
arm.data.transform(M)
bpy.context.view_layer.update()
mid = (arm.data.bones['foot.L'].head_local + arm.data.bones['foot.R'].head_local) / 2.0
R['pivot']['ankle_mid_after_apply'] = [round(x, 9) for x in mid]
assert max(abs(mid.x), abs(mid.y)) < 1e-7, mid
log('pivot ok', R['pivot'])

# ---- 9 re-normalise decimated weights, parent + armature modifier
for tag, ob in lod_objs.items():
    R['weight_stats_' + tag] = rebuild_weights(ob)
for tag, fname, target, ratio, _o, _n, want_anim in LODS:
    ob = pick(tag)
    for md in list(ob.modifiers):
        if md.type == 'ARMATURE': ob.modifiers.remove(md)
    md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    ob.parent = arm
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
R['mesh_world_identity_final'] = (mob.matrix_world == Matrix.Identity(4))
assert R['mesh_world_identity_final']

# ---- 10 per-LOD texture budget
def resize_images(other_px, normal_px):
    changed = []
    for img in list(bpy.data.images):
        if '.tif-' in img.name and img.users == 0:
            bpy.data.images.remove(img)      # exporter-generated combined maps
            continue
        n = img.name
        if not n.endswith('.tif'): continue
        w, h = img.size
        if w == 0 or h == 0: continue
        want = normal_px if n.endswith('_Normal.tif') else other_px
        if (w, h) != (want, want):
            assert want <= w, 'monotonic shrink only: %s %s -> %s' % (n, w, want)
            img.scale(want, want); changed.append([n, [w, h], [want, want]])
    return changed

def prep_name(target_ob):
    for i, o in enumerate(all_meshes):
        if o is not target_ob:
            o.name = '_src%d' % i; o.data.name = '_src%d' % i
    target_ob.name = 'DragonMan_Game'
    target_ob.data.name = 'DragonMan_Game'

# ---- 11 export
COMMON = dict(export_format='GLB', use_selection=True, use_visible=False,
    export_apply=False, export_yup=True, export_texcoords=True, export_normals=True, export_tangents=False,
    export_materials='EXPORT', export_image_format='JPEG', export_image_quality=90, export_jpeg_quality=90,
    export_skins=True, export_def_bones=False, export_influence_nb=4, export_all_influences=False,
    export_rest_position_armature=True, export_leaf_bone=False, export_hierarchy_flatten_bones=False,
    export_anim_slide_to_zero=True, export_frame_range=False,
    export_optimize_animation_size=False, export_optimize_animation_keep_anim_armature=True,
    export_animation_mode='ACTIONS', export_anim_single_armature=True,
    export_force_sampling=True, export_morph=False, export_cameras=False, export_lights=False,
    export_extras=False)

arm.data.pose_position = 'POSE'
R['exports'] = {}
for tag, fname, target, ratio, other_px, normal_px, want_anim in LODS:
    ob = pick(tag)
    prep_name(ob)
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True); ob.select_set(True)
    bpy.context.view_layer.objects.active = arm
    sc.frame_set(1); bpy.context.view_layer.update()
    resized = resize_images(other_px, normal_px)
    path = os.path.join(OUTDIR, fname)
    bpy.ops.export_scene.gltf(filepath=path, export_animations=want_anim, **COMMON)
    R['exports'][tag] = {'file': fname, 'path': path, 'bytes': os.path.getsize(path),
                         'sha256': sha256(path), 'tri_target': target, 'tris': tris(ob),
                         'verts': len(ob.data.vertices), 'tex_other_px': other_px,
                         'tex_normal_px': normal_px, 'animations': want_anim,
                         'resized_images': resized}
    log('exported', fname, R['exports'][tag]['bytes'], 'bytes, tris', R['exports'][tag]['tris'],
        'tex', other_px, normal_px)

R['elapsed_s'] = round(time.time() - t0, 1)
with open(REPORT, 'w', encoding='utf-8') as fh:
    json.dump(R, fh, ensure_ascii=False, indent=1)
log('BUILD OK', R['elapsed_s'], 's')
