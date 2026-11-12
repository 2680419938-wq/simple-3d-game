# -*- coding: utf-8 -*-
r"""m2: retarget the accepted 32-bone Walk (dragon-men-game-walk\DragonMan_Game.glb) onto the
70-bone Mixamo rig, optionally deleting the two knee armour plates.
stage extract -> merge\_work\src_walk.json ; stage apply -> target blend.
"""
import bpy, bmesh, sys, json, os, math, collections
import numpy as np
from mathutils import Matrix, Vector

SRCGLB = r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
WORK = r'D:\ai\建模\dragon-men-rebuild\joint-work\merge\_work'
os.makedirs(WORK, exist_ok=True)
SRCJSON = os.path.join(WORK, 'src_walk.json')

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = {argv[i].lstrip('-'): argv[i + 1] for i in range(0, len(argv) - 1, 2)}
STAGE = opt.get('stage', 'extract')

MAP = {'root': 'mixamorig:Root', 'pelvis': 'mixamorig:Hips', 'spine': 'mixamorig:Spine',
       'chest': 'mixamorig:Spine2', 'neck': 'mixamorig:Neck', 'head': 'mixamorig:Head',
       'tail.001': 'mixamorig:tail.001', 'tail.002': 'mixamorig:tail.002', 'tail.003': 'mixamorig:tail.003',
       'tail.004': 'mixamorig:tail.004', 'tail.005': 'mixamorig:tail.005', 'tail.006': 'mixamorig:tail.006'}
for a, b in (('L', 'Left'), ('R', 'Right')):
    MAP['shoulder.' + a] = 'mixamorig:%sShoulder' % b
    MAP['upper_arm.' + a] = 'mixamorig:%sArm' % b
    MAP['forearm.' + a] = 'mixamorig:%sForeArm' % b
    MAP['hand.' + a] = 'mixamorig:%sHand' % b
    MAP['thigh.' + a] = 'mixamorig:%sUpLeg' % b
    MAP['shin.' + a] = 'mixamorig:%sLeg' % b
    MAP['foot.' + a] = 'mixamorig:%sFoot' % b
    MAP['toe.01.' + a] = 'mixamorig:%sToeBase' % b
    MAP['toe.02.' + a] = 'mixamorig:%sToe02End' % b
    MAP['toe.03.' + a] = 'mixamorig:%sToe03Base' % b

def M16(m):
    return [round(float(m[r][c]), 9) for r in range(4) for c in range(4)]

def M4(a):
    return Matrix(((a[0], a[1], a[2], a[3]), (a[4], a[5], a[6], a[7]),
                   (a[8], a[9], a[10], a[11]), (a[12], a[13], a[14], a[15])))

# ---------------- stage extract ----------------
if STAGE == 'extract':
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.fps, sc.render.fps_base = 30, 1.0
    bpy.ops.import_scene.gltf(filepath=SRCGLB)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    print('[M2] imported armature', arm.name, 'bones', len(arm.data.bones))
    print('[M2] actions', [a.name for a in bpy.data.actions])
    act = [a for a in bpy.data.actions if 'walk' in a.name.lower()][0]
    if arm.animation_data is None: arm.animation_data_create()
    arm.animation_data.action = act
    f0, f1 = [int(round(x)) for x in act.frame_range]
    names = sorted(b.name for b in arm.data.bones)
    rest = {n: M16(arm.data.bones[n].matrix_local) for n in names}
    frames = []
    for f in range(f0, f1 + 1):
        sc.frame_set(0); sc.frame_set(f); bpy.context.view_layer.update()
        frames.append({n: M16(arm.pose.bones[n].matrix) for n in names})
    out = {'glb': SRCGLB, 'action': act.name, 'frame_range': [f0, f1], 'nf': len(frames),
           'fps': 30, 'bones': names, 'rest': rest, 'frames': frames,
           'arm_matrix_world': [[float(v) for v in r] for r in arm.matrix_world]}
    json.dump(out, open(SRCJSON, 'w'))
    print('[M2] extracted %d frames %d..%d from %s -> %s' % (len(frames), f0, f1, act.name, SRCJSON))
    print('[M2] DONE extract')
    sys.exit(0)

# ---------------- stage apply ----------------
SRC = opt['src']; DST = opt['dst']; REPORT = opt['report']
PLATES = opt.get('plates', 'keep'); ROT = int(opt.get('rot', 0))
S = json.load(open(SRCJSON))
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']; body = bpy.data.objects['DragonMan_Body']
feet = {s: bpy.data.objects['DragonMan_Foot.' + s] for s in 'LR'}
R = {'src_blend': SRC, 'dst_blend': DST, 'src_glb': S['glb'], 'src_action': S['action'],
     'plates': PLATES, 'frames': S['nf'], 'mapping': {}, 'notes': []}
sc = bpy.context.scene; sc.render.fps, sc.render.fps_base = 30, 1.0

# ---- delete knee plates
def mesh_world(ob):
    me = ob.data; n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    MW = np.array(ob.matrix_world); return co @ MW[:3, :3].T + MW[:3, 3]

if PLATES == 'delete':
    me = body.data
    adj = collections.defaultdict(set)
    for e in me.edges:
        a0, b0 = int(e.vertices[0]), int(e.vertices[1]); adj[a0].add(b0); adj[b0].add(a0)
    seen = set(); comps = []
    for v0 in range(len(me.vertices)):
        if v0 in seen: continue
        stack = [v0]; comp = []; seen.add(v0)
        while stack:
            v = stack.pop(); comp.append(v)
            for nb in adj[v]:
                if nb not in seen: seen.add(nb); stack.append(nb)
        if len(comp) >= 150: comps.append(comp)
    gn = {g.index: g.name for g in body.vertex_groups}
    tgt_verts = set()
    plate_info = []
    for comp in comps:
        dom = collections.Counter()
        for vi in comp:
            gs = me.vertices[vi].groups
            if gs:
                b = max(gs, key=lambda g: g.weight); dom[gn.get(b.group, '?')] += 1
        top, cnt = dom.most_common(1)[0]
        if top in ('mixamorig:LeftLeg', 'mixamorig:RightLeg') and cnt == len(comp) and 200 <= len(comp) <= 320:
            tgt_verts.update(comp)
            co = np.array([list(me.vertices[vi].co) for vi in comp]) @ np.array(body.matrix_world)[:3, :3].T + np.array(body.matrix_world)[:3, 3]
            plate_info.append({'n': len(comp), 'dom': top, 'bbox': [np.round(co.min(0), 4).tolist(), np.round(co.max(0), 4).tolist()]})
    assert len(plate_info) == 2, plate_info
    v0 = len(me.vertices); f0 = len(me.polygons)
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    delv = [bm.verts[i] for i in sorted(tgt_verts)]
    bmesh.ops.delete(bm, geom=delv, context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    R['plates_removed'] = plate_info
    R['body_verts'] = [v0, len(me.vertices)]; R['body_faces'] = [f0, len(me.polygons)]
    print('[M2] plates removed %s  verts %d->%d faces %d->%d' % (
        [(p['n'], p['dom']) for p in plate_info], v0, len(me.vertices), f0, len(me.polygons)))

# ---- pose target to rest and gather rest matrices
if arm.animation_data is None: arm.animation_data_create()
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
    pb.rotation_mode = 'QUATERNION'
bpy.context.view_layer.update()
TB = {b.name: b for b in arm.data.bones}
rest_t = {n: b.matrix_local.copy() for n, b in TB.items()}
rest_tn = {n: np.array(rest_t[n]) for n in TB}
par = {n: (TB[n].parent.name if TB[n].parent else None) for n in TB}

# ---- mapping + rigid frame map C (target armature space A -> source space S)
pairs = [(s, t) for s, t in MAP.items() if s in S['rest'] and t in TB]
R['mapping'] = {s: t for s, t in pairs}
R['unmapped_src'] = [s for s in S['bones'] if s not in MAP]
rest_s = {s: M4(S['rest'][s]) for s, _ in pairs}
# rotation: average of R_S(b) @ R_A(b)^T  (bone axes are rigidly related between the two rest rigs)
Acc = np.zeros((3, 3))
for s, t in pairs:
    Rs = np.array(rest_s[s].to_3x3().normalized()); Ra = np.array(rest_t[t].to_3x3().normalized())
    Acc += Rs @ Ra.T
U, sv, Vt = np.linalg.svd(Acc)
Crot = U @ Vt
if np.linalg.det(Crot) < 0: Crot = U @ np.diag([1, 1, -1]) @ Vt
heads_s = np.array([np.array(rest_s[s])[:3, 3] for s, _ in pairs])
heads_a = np.array([rest_tn[t][:3, 3] for _, t in pairs])
# A (armature-local, carries the rig's 1.5 object scale) -> S (metres): uniform scale + rot + t
as_ = heads_s - heads_s.mean(0); aa = heads_a - heads_a.mean(0)
cscale = float((as_ * (aa @ Crot.T)).sum() / max(1e-12, (aa * aa).sum()))
tvec = heads_s.mean(0) - cscale * (Crot @ heads_a.mean(0))
C_AS = Matrix.Translation(Vector(tvec)) @ Matrix(Crot.tolist()).to_4x4() @ Matrix.Scale(cscale, 4)
C_SA = C_AS.inverted()
mapped_dev = max(float(np.max(np.abs(np.array(C_AS @ rest_t[t]) - np.array(rest_s[s])))) for s, t in pairs)
R['frame_map'] = {'rot': [[round(float(v), 6) for v in r] for r in Crot], 'scale': cscale,
                  't': [round(float(v), 6) for v in tvec], 'mapped_rest_dev': mapped_dev}
print('[M2] frame map A->S scale=%.6f rot=%s t=%s  mapped rest max dev %.3e' % (
    cscale, np.round(Crot, 4).tolist(), np.round(tvec, 4), mapped_dev))

# ---- per-frame desired world matrices + basis, then keyframes
SRCB = [(s, t) for s, t in pairs]
inv_src_rest = {s: M4(S['rest'][s]).inverted() for s, _ in SRCB}
# hierarchy order top-down
order = []
def walk(n):
    order.append(n)
    for c in TB[n].children: walk(c.name)
for n in TB:
    if par[n] is None: walk(n)
depth = {}
def setd(n, d):
    depth[n] = d
    for c in TB[n].children: setd(c.name, d + 1)
for n in TB:
    if par[n] is None: setd(n, 0)
order = sorted(TB.keys(), key=lambda n: depth[n])

act = bpy.data.actions.new('Walk')
arm.animation_data.action = act
act.use_fake_user = True
idle = bpy.data.actions.get('Idle_Lively')
if idle: idle.use_fake_user = True
nf = S['nf']; f0 = S['frame_range'][0]
first_mats = None; last_mats = None
for fi in range(nf):
    f = fi + 1
    srcf = S['frames'][fi]
    Mdes = {}
    for s, t in SRCB:
        Dsrc = M4(srcf[s]) @ inv_src_rest[s]
        Mdes[t] = C_SA @ Dsrc @ C_AS @ rest_t[t]
    Mpose = {}
    for n in order:
        p = par[n]
        if n in Mdes:
            Mpose[n] = Mdes[n]
        else:
            Mpose[n] = (Mpose[p] @ rest_t[p].inverted() @ rest_t[n]) if p else rest_t[n]
        pbp = arm.pose.bones[n]
        parent_off = (Mpose[p] @ rest_t[p].inverted() @ rest_t[n]) if p else rest_t[n]
        pbp.matrix_basis = parent_off.inverted() @ Mpose[n]
        if pbp.rotation_mode != 'QUATERNION': pbp.rotation_mode = 'QUATERNION'
        pbp.keyframe_insert('location', frame=f, group=n)
        pbp.keyframe_insert('rotation_quaternion', frame=f, group=n)
        pbp.keyframe_insert('scale', frame=f, group=n)
    if fi == 0: first_mats = {k: v.copy() for k, v in Mpose.items()}
    if fi == nf - 1: last_mats = {k: v.copy() for k, v in Mpose.items()}
R['loop_max_delta'] = max(float(np.max(np.abs(np.array(first_mats[k]) - np.array(last_mats[k])))) for k in first_mats)
fcs = []
try:
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                fcs.extend(cb.fcurves)
except Exception as e:
    print('[M2] fcurve walk error', e)
for fc in fcs:
    for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
R['fcurves'] = len(fcs)
print('[M2] Walk keyed frames 1..%d  fcurves %d  loop max delta %.3e' % (nf, len(fcs), R['loop_max_delta']))

# ---- measure
def eval_meshes():
    dg = bpy.context.evaluated_depsgraph_get(); out = []
    for ob in (body, feet['L'], feet['R']):
        ev = ob.evaluated_get(dg); m = ev.to_mesh()
        n = len(m.vertices); co = np.empty(n * 3); m.vertices.foreach_get('co', co); co = co.reshape(n, 3)
        MW = np.array(ev.matrix_world); out.append(co @ MW[:3, :3].T + MW[:3, 3])
        ev.to_mesh_clear()
    return out

def knee_deg(side):
    b = lambda n: np.array(arm.matrix_world @ arm.pose.bones[n].head)
    U = 'mixamorig:%sUpLeg' % side; L = 'mixamorig:%sLeg' % side; F = 'mixamorig:%sFoot' % side
    u1 = b(L) - b(U); u2 = b(F) - b(L)
    u1 /= np.linalg.norm(u1); u2 /= np.linalg.norm(u2)
    return float(math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(u1, u2)))))))

minz = []; knees = []
for f in range(1, nf + 1):
    sc.frame_set(0); sc.frame_set(f); bpy.context.view_layer.update()
    co = np.vstack(eval_meshes())
    minz.append(float(co[:, 2].min())); knees.append((knee_deg('Left'), knee_deg('Right')))
R['min_z'] = [round(v, 6) for v in minz]
R['knee_deg_max'] = [round(max(k[0] for k in knees), 3), round(max(k[1] for k in knees), 3)]
R['knee_deg_all_L'] = [round(k[0], 2) for k in knees]
R['knee_deg_all_R'] = [round(k[1], 2) for k in knees]
LIFTUR = 0.0
if min(minz) < 0:
    LIFTUR = -min(minz) + 1e-4
    R['notes'].append('lifted root by %.6f m' % LIFTUR)
    for n in [n for n in TB if par[n] is None]:
        for f in range(1, nf + 1):
            sc.frame_set(0); sc.frame_set(f); bpy.context.view_layer.update()
            pb = arm.pose.bones[n]
            pb.location = pb.location + (rest_t[n].to_3x3().inverted() @ Vector((0, 0, LIFTUR)))
            pb.keyframe_insert('location', frame=f, group=n)
    minz = []
    for f in range(1, nf + 1):
        sc.frame_set(0); sc.frame_set(f); bpy.context.view_layer.update()
        minz.append(float(np.vstack(eval_meshes())[:, 2].min()))
    R['min_z_after_lift'] = [round(v, 6) for v in minz]
print('[M2] min z %s  knee max L%.2f R%.2f' % (round(min(minz), 6), R['knee_deg_max'][0], R['knee_deg_max'][1]))

# ---- restore idle as active action, T-pose-ish frame 1
sc.frame_set(1)
sc.frame_start = 1; sc.frame_end = 121
bpy.ops.wm.save_as_mainfile(filepath=DST)
json.dump(R, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[M2] saved', DST)
print('[M2] DONE apply')
