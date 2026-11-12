# -*- coding: utf-8 -*-
"""Probe 2: dominant shell vertex sets + shell gap vs knee bend (armature blend)."""
import bpy, math, sys
import numpy as np
from mathutils import Matrix, Vector
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\walk-work\scripts')
import walklib as W

BLEND = r'D:\ai\建模\dragon-men-rebuild\armor-work\DragonMan_Armor.blend'
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
S = arm.matrix_world.to_scale().x
print('[P] constraints:')
for pb in arm.pose.bones:
    for c in pb.constraints:
        print('   ', pb.name, c.type, getattr(c, 'object', None).name if getattr(c,'object',None) else '', c.name)
meshes = W.char_meshes()
body = bpy.data.objects['DragonMan_Body']
gn = [g.name for g in body.vertex_groups]
dom = {}
for i, v in enumerate(body.data.vertices):
    bw = -1.0; bi = -1
    for g in v.groups:
        if g.weight > bw: bw = g.weight; bi = g.group
    dom.setdefault(gn[bi], []).append(i)
print('[P] body groups:', {k: len(v) for k, v in sorted(dom.items())})
for nm in ['armor_knee.L','armor_knee.R']:
    if nm in gn: print('[P] group', nm, 'nverts', len(dom.get(nm, [])))

def set_idx(names, objs):
    out = {}
    for o in objs:
        g = [vg.name for vg in o.vertex_groups]
        acc = {n: [] for n in names}
        for i, v in enumerate(o.data.vertices):
            bw = -1.0; bi = -1
            for gv in v.groups:
                if gv.weight > bw: bw = gv.weight; bi = gv.group
            n = g[bi]
            if n in acc: acc[n].append(i)
        out[o.name] = (acc, o)
    return out

def verts_named(side):
    """world coords of thigh-dominant vs shin/foot/toe-dominant vertices, over body+feet"""
    res = {'thigh': [], 'shin': []}
    per = {}
    for o in meshes:
        co = W.evworld(o)
        g = [vg.name for vg in o.vertex_groups]
        mine = {'thigh': [], 'shin': []}
        for i, v in enumerate(o.data.vertices):
            bw = -1.0; bi = -1
            for gv in v.groups:
                if gv.weight > bw: bw = gv.weight; bi = gv.group
            n = g[bi]
            if n == 'thigh.' + side: mine['thigh'].append(i)
            elif n in ('shin.'+side, 'foot.'+side) or n.startswith('toe.') and n.endswith('.'+side): mine['shin'].append(i)
        res['thigh'].append(co[mine['thigh']]); res['shin'].append(co[mine['shin']])
        per[o.name] = {k: len(v) for k, v in mine.items()}
    return np.vstack(res['thigh']), np.vstack(res['shin']), per

def mind(A, B, chunk=256):
    best = 1e9
    for i in range(0, len(A), chunk):
        d = np.linalg.norm(A[i:i+chunk, None, :] - B[None, :, :], axis=2)
        best = min(best, float(d.min()))
    return best

def gap(side):
    T, S_, per = verts_named(side)
    return mind(T, S_), len(T), len(S_)

print('[P] === SET SIZES (rest) ===')
for s in 'LR':
    g, nt, ns = gap(s)
    T, Sh, per = verts_named(s)
    print('[P] %s thigh %d verts  shin/foot/toe %d verts  rest gap %.5f  | thigh bbox x[%.3f,%.3f] z[%.3f,%.3f] | shin bbox x[%.3f,%.3f] z[%.3f,%.3f]'
          % (s, nt, ns, g, T[:,0].min(), T[:,0].max(), T[:,2].min(), T[:,2].max(),
             Sh[:,0].min(), Sh[:,0].max(), Sh[:,2].min(), Sh[:,2].max()))
    print('[P]   per-object counts', per)

# idle f1 with action
arm.animation_data.action = bpy.data.actions['Idle_Lively']
sc.frame_set(0); sc.frame_set(1); bpy.context.view_layer.update()
print('[P] === IDLE f1 ===')
for s in 'LR':
    g, nt, ns = gap(s)
    print('[P] idle f1 %s gap %.5f' % (s, g))
arm.animation_data.action = bpy.data.actions['Walk']
sc.frame_set(0); sc.frame_set(1); bpy.context.view_layer.update()
print('[P] === WALK f11 (max bend) ===')
sc.frame_set(11); bpy.context.view_layer.update()
for s in 'LR':
    print('[P] walk f11 %s gap %.5f' % (s, gap(s)[0]))

# now sweep knee bend with the production direction-based pose builder
arm.animation_data.action = None
W.reset_pose(arm)
B = arm.data.bones
wr = lambda v: Vector(v)*S
REST = {b.name: (wr(b.head_local), wr(b.tail_local)) for b in B}
PELV = REST['pelvis'][0]; HIP = {s: REST['thigh.'+s][0] for s in 'LR'}
Lt = {s: B['thigh.'+s].length*S for s in 'LR'}; Ls = {s: B['shin.'+s].length*S for s in 'LR'}
print('[P] rest hip L', tuple(round(x,4) for x in HIP['L']), 'R', tuple(round(x,4) for x in HIP['R']))

print('[P] === KNEE SWEEP (thigh vertical, shin bent by theta toward -X? and +X) ===')
for thpitch in (0.0, 8.0, -8.0):
    for bend in (0, 5, 10, 15, 20, 25, 30, 40):
        tgt = {}
        fw = Vector((-math.sin(math.radians(thpitch)), 0, -math.cos(math.radians(thpitch))))
        for s in 'LR':
            tgt['thigh.'+s] = fw
            # shin rotated by bend around Y: toward -X (forward toe) keeps knee behind
            a = math.radians(thpitch) + math.radians(bend)
            tgt['shin.'+s] = Vector((-math.sin(a), 0, -math.cos(a)))
            tgt['foot.'+s] = Vector((-1.0, 0, 0))
        M = W.build_pose(arm, tgt)
        W.apply_pose(arm, M)
        out = []
        for s in 'LR':
            g = gap(s)[0]
            pb = arm.pose.bones['thigh.'+s]; sb = arm.pose.bones['shin.'+s]
            real = math.degrees((pb.tail-pb.head).angle(sb.tail-sb.head))
            out.append('%s %.5f (real %.1f)' % (s, g, real))
        print('[P] thighpitch %+4.1f bend %2d -> gap %s' % (thpitch, bend, ' | '.join(out)))
