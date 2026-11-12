# fix_limbs.py -- (A) claw verts become rigid single-bone, (B) thigh top ring blends toward Hips
import bpy, sys, os, json
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

SRC, OUTB = O['src'], O['out-blend']
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
report = {'claw': {}, 'thigh': {}}

def vmat_names(ob):
    me = ob.data
    counts = {}
    for poly in me.polygons:
        for vi in poly.vertices:
            counts.setdefault(vi, {})
            counts[vi][poly.material_index] = counts[vi].get(poly.material_index, 0) + 1
    names = [m.name if m else '' for m in me.materials]
    out = []
    for vi in range(len(me.vertices)):
        d = counts.get(vi)
        out.append(names[max(d.items(), key=lambda kv: kv[1])[0]] if d else '')
    return out

for ob in bpy.data.objects:
    if ob.type != 'MESH' or ob.name.startswith('WGT_'):
        continue
    me = ob.data
    n = len(me.vertices)
    mats = vmat_names(ob)
    gname = {g.index: g.name for g in ob.vertex_groups}
    per_vert = []
    for v in me.vertices:
        per_vert.append([(gname.get(g.group, ''), g.weight) for g in v.groups if g.weight > 0])

    # ---- A: rigid claws ----
    claw_idx = [i for i in range(n) if mats[i] == 'DragonMan_Claw']
    fixed = 0
    for vi in claw_idx:
        w = per_vert[vi]
        if not w:
            continue
        w.sort(key=lambda x: -x[1])
        top = w[0][0]
        if len(w) > 1 and sum(x[1] for x in w) > 0 or len(w) > 1:
            for nm, _ in w:
                if nm == top:
                    ob.vertex_groups[nm].add([vi], 1.0, 'REPLACE')
                else:
                    ob.vertex_groups[nm].remove([vi])
            fixed += 1
    report['claw'][ob.name] = {'verts': len(claw_idx), 'made_rigid': fixed}

    # ---- B: thigh top ring -> blend with Hips ----
    hips_name = 'mixamorig:Hips'
    for side, upleg in (('L', 'mixamorig:LeftUpLeg'), ('R', 'mixamorig:RightUpLeg')):
        gi = ob.vertex_groups.get(upleg)
        if gi is None:
            continue
        idx = [i for i in range(n) if any(nm == upleg and wt > 0.2 for nm, wt in per_vert[i])]
        if len(idx) < 50:
            continue
        co = np.array([me.vertices[i].co[:] for i in idx])
        zmaxo = co[:, 2].max()
        band = (co[:, 2] > zmaxo - 0.06)  # top 6 cm of the thigh block
        hipsg = ob.vertex_groups.get(hips_name) or ob.vertex_groups.new(name=hips_name)
        cnt = 0
        for k, vi in enumerate(idx):
            if not band[k]:
                continue
            t = (zmaxo - co[k, 2]) / 0.06          # 0 at the very top, 1 at 6 cm down
            hips_w = 0.45 * max(0.0, 1.0 - t)      # up to 45% Hips at the rim
            if hips_w <= 0.01:
                continue
            cur = dict((nm, wt) for nm, wt in per_vert[vi])
            upleg_w = cur.get(upleg, 0.0) * (1.0 - hips_w)
            hipsg.add([vi], hips_w, 'REPLACE')
            ob.vertex_groups[upleg].add([vi], upleg_w, 'REPLACE')
            cnt += 1
        report['thigh'][ob.name + '.' + side] = {'thigh_verts': len(idx), 'blended': cnt, 'top_z': round(float(zmaxo), 4)}

bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[FL] saved', OUTB)
print('[FL]', json.dumps(report, ensure_ascii=False)[:800])
if O.get('report'):
    json.dump(report, open(O['report'], 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
