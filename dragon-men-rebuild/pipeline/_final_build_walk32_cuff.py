# -*- coding: utf-8 -*-
"""32-bone game package WITHOUT the two knee armour plates: armor blend -> LOD0/LOD1/LOD2
(Idle_Lively+Walk) + TPose (no anim).
Based on pipeline/_final_build_34.py: the plates are deleted from DragonMan_Body before the
join (530 verts / 548 n-gon faces / 1,052 tris), the rig goes back to the standard 32 bones
and the 34-bone plate patches (purity check, SHIP location lift) are dropped.
Run: blender.exe -b --factory-startup -P _final_build_walk32_cuff.py
"""
import bpy, bmesh, json, math, os, hashlib, time
from mathutils import Matrix, Vector

BLEND  = r'D:\ai\建模\dragon-men-rebuild\armor-work\DragonMan_Armor_cuff.blend'
OUTDIR = r'D:\ai\建模\dragon-men-game-walk'
WORK   = r'D:\ai\建模\dragon-men-rebuild\armor-work\verify\walk32_cuff'
REPORT = os.path.join(WORK, '_build_walk32_cuff_report.json')
os.makedirs(OUTDIR, exist_ok=True); os.makedirs(WORK, exist_ok=True)

KEEP = ['root','pelvis','spine','chest','neck','head',
        'shoulder.L','upper_arm.L','forearm.L','hand.L',
        'shoulder.R','upper_arm.R','forearm.R','hand.R',
        'tail.001','tail.002','tail.003','tail.004','tail.005','tail.006',
        'thigh.L','shin.L','foot.L','toe.01.L','toe.02.L','toe.03.L',
        'thigh.R','shin.R','foot.R','toe.01.R','toe.02.R','toe.03.R']
assert len(KEEP) == 32 and len(set(KEEP)) == 32
ANIM_ACTS = ['Idle_Lively', 'Walk']
LODS = [('LOD0', 'DragonMan_Game.glb',      52200, None,  2048, 1024, True),
        ('TPOSE','DragonMan_TPose.glb',     None,  None,  2048, 1024, False),
        ('LOD1', 'DragonMan_Game_LOD1.glb', 26500, 0.500, 1024, 1024, True),
        ('LOD2', 'DragonMan_Game_LOD2.glb', 11650, 0.220,  512,  512, True)]
R = {}
def log(*a): print('[BUILDW32]', *a, flush=True)
def mdiff(m1, m2): return max(abs(a-b) for r1, r2 in zip(m1, m2) for a, b in zip(r1, r2))
def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for c in iter(lambda: fh.read(1 << 20), b''): h.update(c)
    return h.hexdigest().upper()
def tris(ob):
    ob.data.calc_loop_triangles(); return len(ob.data.loop_triangles)

def delete_plates(body):
    """Delete every vertex weighted >=0.999 to armor_knee.L/R plus all faces they own.
    A plate vert shared with suit geometry would punch a hole in the suit, so that case
    is refused instead of silently shipped."""
    me = body.data
    side_of = {body.vertex_groups['armor_knee.' + s].index: s for s in ('L', 'R')}
    sel = {'L': set(), 'R': set()}
    for v in me.vertices:
        w = 0.0
        for g in v.groups:
            if g.group in side_of and g.weight > w: w = g.weight
        if w >= 0.999:
            for g in v.groups:
                if g.group in side_of and g.weight == w: sel[side_of[g.group]].add(v.index)
    both = sel['L'] | sel['R']
    assert not (sel['L'] & sel['R'])
    partial = [p.index for p in me.polygons
               if 0 < len(set(p.vertices) & both) < len(p.vertices)]
    assert not partial, 'plate verts shared with suit geometry: %s' % partial[:8]
    poly_in = [p for p in me.polygons if set(p.vertices) <= both]
    sides = {}
    for p in poly_in:
        k = len(p.vertices); sides[k] = sides.get(k, 0) + 1
    st = {'verts': {'L': len(sel['L']), 'R': len(sel['R'])},
          'polys': {'L': sum(1 for p in poly_in if set(p.vertices) <= sel['L']),
                    'R': sum(1 for p in poly_in if set(p.vertices) <= sel['R'])},
          'face_sides': {str(k): v for k, v in sorted(sides.items())},
          'removed_tris': sum(len(p.vertices) - 2 for p in poly_in)}
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in sorted(both)], context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    st['verts_after'] = len(me.vertices); st['tris_after'] = tris(body)
    assert st['verts'] == {'L': 265, 'R': 265}, st['verts']
    assert st['polys'] == {'L': 274, 'R': 274}, st['polys']
    assert st['tris_after'] == 40588 - st['removed_tris'], st['tris_after']
    return st
def action_fcurves(act):
    out = []
    for lay in act.layers:
        for st in lay.strips:
            for cb in st.channelbags: out.extend(cb.fcurves)
    return out

def goto(f):
    """frame_set is a no-op if f is already current -> stale pose from the previous
    action would be captured/verified. Step away first."""
    sc.frame_set(0); sc.frame_set(f)
    bpy.context.view_layer.update()

t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene; sc.render.fps, sc.render.fps_base = 30, 1.0
arm = bpy.data.objects['DragonMan_Rig']
meshes = [bpy.data.objects[n] for n in ['DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R']]
R['source_blend'] = BLEND; R['source_sha256'] = sha256(BLEND)
R['bones_before'] = len(arm.data.bones)
R['tris_before'] = [tris(o) for o in meshes]
assert R['tris_before'] == [40588, 6332, 6332], R['tris_before']

# 1b drop the two knee armour plates from the body BEFORE the join
R['plates'] = delete_plates(meshes[0])
R['tris_after_plate_delete'] = [tris(o) for o in meshes]
assert R['tris_after_plate_delete'] == [40588 - R['plates']['removed_tris'], 6332, 6332], \
    R['tris_after_plate_delete']
log('plates removed', R['plates'])

# 1 widgets out
for n in ('WGT_pole', 'WGT_ring', 'WGT_root'):
    ob = bpy.data.objects.get(n)
    if ob: bpy.data.objects.remove(ob, do_unlink=True)

# 2 join + flatten
bpy.ops.object.select_all(action='DESELECT')
for ob in meshes: ob.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()
mob = meshes[0]
Rm = mob.matrix_world.copy(); Ram = arm.matrix_world.copy()
for ob, M0 in ((mob, Rm), (arm, Ram)):
    ob.parent = None; ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4); ob.data.transform(M0)
bpy.context.view_layer.update()
R['materials'] = [m.name for m in mob.data.materials]
R['tris_joined'] = tris(mob)
assert R['tris_joined'] == 52200 and len(R['materials']) == 4
log('join ok', R['tris_joined'], R['materials'])

# 2.5 replace the source Walk action with the rebuilt knee<=25 deg gait
# (33 frames x 32 bones matrix_basis, bone-local -> frame invariant, generated by _walkgen32.py)
NEWWALK = r'D:\ai\建模\dragon-men-rebuild\armor-work\walk_new_basis.json'
NW = json.load(open(NEWWALK))
assert NW['nf'] == 33 and len(NW['frames']) == 33, NW['nf']
assert sorted(NW['bones']) == sorted(KEEP), 'bone name mismatch'
# posed from the FINAL 32-bone hierarchy (see step 6): the exported GLB the basis was
# generated against already has the post-deletion hierarchy, so authoring must wait for it.

# 3 capture pose matrices for BOTH actions over their frame ranges
# remove IK/control constraints first (FK default; avoids depsgraph errors after bone deletion)
ncon0 = 0
for pb in arm.pose.bones:
    for c in list(pb.constraints): pb.constraints.remove(c); ncon0 += 1
R['constraints_removed_precapture'] = ncon0
arm.data.pose_position = 'POSE'
SRC_ACTS = {n: bpy.data.actions[n] for n in ANIM_ACTS}
RANGES = {'Idle_Lively': (1, 121), 'Walk': (1, 33)}
rec = {}
for an in ANIM_ACTS:
    arm.animation_data.action = SRC_ACTS[an]
    f0, f1 = RANGES[an]; frames = list(range(f0, f1 + 1))
    seq = []
    for f in frames:
        goto(f)
        seq.append({n: arm.pose.bones[n].matrix.copy() for n in KEEP})
    rec[an] = (frames, seq)
R['captured'] = {an: len(rec[an][0]) for an in ANIM_ACTS}
log('captured', R['captured'])

# 4 weights merge removed-bone groups -> nearest kept ancestor, cap 4, normalise
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
        t = kept_anc(b.name); assert t in KEEP, (b.name, t); merge_map[b.name] = t
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
            nm = gn[g.group]; tgt = nm if nm in KEEP else merge_map[nm]
            d[tgt] = d.get(tgt, 0.0) + g.weight
        if not d: d = {'pelvis': 1.0}; st['zero'] += 1
        items = sorted(d.items(), key=lambda kv: -kv[1])[:4]
        tot = sum(w for _, w in items); items = [(k, w / tot) for k, w in items]
        newW.append(items); st['max_inf'] = max(st['max_inf'], len(items))
        s = sum(w for _, w in items); st['sum_min'] = min(st['sum_min'], s); st['sum_max'] = max(st['sum_max'], s)
    ob.vertex_groups.clear()
    vgs = {n: ob.vertex_groups.new(name=n) for n in KEEP}
    for i, ws in enumerate(newW):
        for nm, w in ws: vgs[nm].add([i], w, 'REPLACE')
    return st
R['weight_stats_LOD0'] = rebuild_weights(mob)
R['armor_groups_after_join'] = [vg.name for vg in mob.vertex_groups if 'armor' in vg.name]
assert not R['armor_groups_after_join'], R['armor_groups_after_join']

# 5 delete bones + constraints
bpy.context.view_layer.objects.active = arm
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
for b in eb: b.use_connect = False
pre = {n: (eb[n].head.copy(), eb[n].tail.copy()) for n in KEEP}
for n in [b.name for b in eb if b.name not in KEEP]: eb.remove(eb[n])
bpy.ops.object.mode_set(mode='OBJECT'); bpy.context.view_layer.update()
R['bones_after'] = len(arm.data.bones)
assert set(b.name for b in arm.data.bones) == set(KEEP)
drift = max(max((arm.data.bones[n].head_local - pre[n][0]).length,
                (arm.data.bones[n].tail_local - pre[n][1]).length) for n in KEEP)
R['rest_drift'] = float('%.3e' % drift); assert drift < 1e-6
ncon = 0
for pb in arm.pose.bones:
    for c in list(pb.constraints): pb.constraints.remove(c); ncon += 1
R['constraints_removed'] = ncon
log('bones', R['bones_after'], 'drift', R['rest_drift'])

# 6 rebake BOTH actions for the 32-bone rig
for n in KEEP: arm.pose.bones[n].rotation_mode = 'QUATERNION'
basel = {n: arm.data.bones[n].matrix_local.copy() for n in KEEP}
# --- walk: authored from walk_new_basis.json in the final hierarchy (bone-local, frame invariant)
BONE = {b.name: b for b in arm.data.bones}
NW_PAR = {n: (BONE[n].parent.name if BONE[n].parent else None) for n in KEEP}
assert all(p is None or p in KEEP for p in NW_PAR.values()), \
    {n: p for n, p in NW_PAR.items() if p is not None and p not in KEEP}

def nw_basis(m):
    return Matrix(((m[0], m[1], m[2], m[3]), (m[4], m[5], m[6], m[7]),
                   (m[8], m[9], m[10], m[11]), (m[12], m[13], m[14], m[15])))

def nw_snap(fr):
    out = {}; todo = list(KEEP)
    while todo:
        for n in list(todo):
            p = NW_PAR[n]; B = nw_basis(fr[n])
            if p is None:
                out[n] = basel[n] @ B
            elif p in out:
                out[n] = out[p] @ (basel[p].inverted() @ basel[n]) @ B
            else:
                continue
            todo.remove(n)
    return out

def nw_basis_of(n, snap):
    p = NW_PAR[n]
    if p is None: return basel[n].inverted() @ snap[n]
    rel = basel[p].inverted() @ basel[n]
    return rel.inverted() @ (snap[p].inverted() @ snap[n])

NW_SNAP = [nw_snap(fr) for fr in NW['frames']]
nw_err = 0.0
for i, fr in enumerate(NW['frames']):
    for n in KEEP:
        M = nw_basis_of(n, NW_SNAP[i])
        nw_err = max(nw_err, max(abs(M[r][c] - fr[n][r * 4 + c]) for r in range(4) for c in range(4)))
print('NWERR %.3e' % nw_err)
assert nw_err < 1e-5, nw_err
R['walk_new'] = {'json': NEWWALK, 'frames': 33, 'basis_roundtrip_err': float('%.3e' % nw_err)}
rec['Walk'] = (rec['Walk'][0], NW_SNAP)
log('new walk pose authored', R['walk_new'])
new_acts = {}
for an in ANIM_ACTS:
    frames, seq = rec[an]
    arm.animation_data.action = None
    act = bpy.data.actions.new('_new_' + an); arm.animation_data.action = act
    for fi, f in enumerate(frames):
        snap = seq[fi]
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
    # linear interp for Walk armor smoothness; keep all LINEAR like source walk
    for fc in action_fcurves(act):
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
        fc.update()
    new_acts[an] = act
# purge old actions (named Idle_Lively/Walk, reference deleted bones); new ones are _new_*
arm.animation_data.action = None
for a in list(bpy.data.actions):
    if not a.name.startswith('_new_'): bpy.data.actions.remove(a)
for an in ANIM_ACTS:
    new_acts[an].name = an
# bake error check
err = {}
for an in ANIM_ACTS:
    frames, seq = rec[an]; arm.animation_data.action = new_acts[an]; e = 0.0
    for fi, f in enumerate(frames):
        goto(f)
        for n in KEEP: e = max(e, mdiff(arm.pose.bones[n].matrix, seq[fi][n]))
    err[an] = float('%.3e' % e); assert e < 1e-5, (an, e)
R['bake_max_err'] = err
R['action_ranges'] = {an: [round(x, 3) for x in new_acts[an].frame_range] for an in ANIM_ACTS}
log('bake ok', err)

# 7 LOD decimate
def make_lod(src, name, target, base_ratio):
    ratio = base_ratio; tries = []
    for _it in range(7):
        ob = src.copy(); ob.data = src.data.copy(); ob.name = name; ob.data.name = name
        bpy.context.collection.objects.link(ob)
        for m in list(ob.modifiers):
            if m.type == 'ARMATURE': ob.modifiers.remove(m)
        md = ob.modifiers.new('DEC', 'DECIMATE'); md.decimate_type = 'COLLAPSE'
        md.ratio = ratio; md.use_collapse_triangulate = True
        bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=md.name)
        n = tris(ob); tries.append([round(ratio, 5), n])
        if abs(n - target) <= 150: return ob, tries, n
        bpy.data.objects.remove(ob, do_unlink=True)
        ratio = max(0.01, min(0.999, ratio * float(target) / float(n)))
    raise RuntimeError('decimate fail %s' % tries)
lod_objs = {}; R['decimate'] = {}
for tag, fname, target, ratio, _o, _n, _a in LODS:
    if ratio is None: continue
    ob, tries, n = make_lod(mob, tag, target, ratio)
    lod_objs[tag] = ob; R['decimate'][tag] = {'target': target, 'achieved': n, 'tries': tries}
    log('decimate', tag, '->', n)
def pick(tag): return mob if tag in ('LOD0', 'TPOSE') else lod_objs[tag]

# 8 pivot ankle midpoint -> origin, sole -> z=0
all_meshes = [mob, lod_objs['LOD1'], lod_objs['LOD2']]
ank = (arm.data.bones['foot.L'].head_local + arm.data.bones['foot.R'].head_local) / 2.0
minz = min(min(v.co.z for v in o.data.vertices) for o in all_meshes)
Rz = Matrix(((0.,-1.,0.,0.),(1.,0.,0.,0.),(0.,0.,1.,0.),(0.,0.,0.,1.)))
t = Vector((ank.y, -ank.x, -minz)); M = Matrix.Translation(t) @ Rz
chk = M @ ank
R['pivot_residual_xy'] = float('%.3e' % max(abs(chk.x), abs(chk.y))); assert max(abs(chk.x), abs(chk.y)) < 1e-9
for ob in all_meshes: ob.data.transform(M)
arm.data.transform(M); bpy.context.view_layer.update()
mid = (arm.data.bones['foot.L'].head_local + arm.data.bones['foot.R'].head_local) / 2.0
assert max(abs(mid.x), abs(mid.y)) < 1e-7
log('pivot ok')

# 9 renormalise LOD weights + parent/armature modifier
for tag, ob in lod_objs.items(): R['weight_stats_' + tag] = rebuild_weights(ob)
for tag, fname, target, ratio, _o, _n, want_anim in LODS:
    ob = pick(tag)
    for md in list(ob.modifiers):
        if md.type == 'ARMATURE': ob.modifiers.remove(md)
    md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    ob.parent = arm; ob.matrix_parent_inverse = Matrix.Identity(4); ob.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()

# 10 texture budget
def resize_images(other_px, normal_px):
    changed = []
    for img in list(bpy.data.images):
        if '.tif-' in img.name and img.users == 0: bpy.data.images.remove(img); continue
        n = img.name
        if not n.endswith('.tif'): continue
        w, h = img.size
        if w == 0 or h == 0: continue
        want = normal_px if n.endswith('_Normal.tif') else other_px
        if (w, h) != (want, want):
            assert want <= w; img.scale(want, want); changed.append([n, [w, h], [want, want]])
    return changed
def prep_name(target_ob):
    for i, o in enumerate(all_meshes):
        if o is not target_ob: o.name = '_src%d' % i; o.data.name = '_src%d' % i
    target_ob.name = 'DragonMan_Game'; target_ob.data.name = 'DragonMan_Game'

# 11 export
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
# ensure both actions present & fake_user so exporter picks them up
for an in ANIM_ACTS: new_acts[an].use_fake_user = True
R['exports'] = {}
for tag, fname, target, ratio, other_px, normal_px, want_anim in LODS:
    ob = pick(tag); prep_name(ob)
    bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); ob.select_set(True)
    bpy.context.view_layer.objects.active = arm
    sc.frame_set(1); bpy.context.view_layer.update()
    resized = resize_images(other_px, normal_px)
    path = os.path.join(OUTDIR, fname)
    bpy.ops.export_scene.gltf(filepath=path, export_animations=want_anim, **COMMON)
    R['exports'][tag] = {'file': fname, 'bytes': os.path.getsize(path), 'sha256': sha256(path),
                         'tris': tris(ob), 'verts': len(ob.data.vertices),
                         'tex_other': other_px, 'tex_normal': normal_px, 'animations': want_anim,
                         'resized': resized}
    log('exported', fname, R['exports'][tag]['bytes'], 'tris', tris(ob))
R['elapsed_s'] = round(time.time() - t0, 1)
json.dump(R, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
log('BUILDW32 OK', R['elapsed_s'], 's')
print("BUILDW32 DONE")
