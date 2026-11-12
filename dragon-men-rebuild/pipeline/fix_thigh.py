# fix_thigh.py -- soften the thigh shells: blend their upper part to Hips, using WORLD-space height
import bpy, sys, json
from mathutils import Vector
a = sys.argv[sys.argv.index('--')+1:]
O = {}
i=0
while i < len(a):
    if a[i].startswith('--'):
        k=a[i].lstrip('-'); v=a[i+1] if i+1<len(a) and not a[i+1].startswith('--') else '1'
        O[k]=v; i+=2 if (i+1<len(a) and not a[i+1].startswith('--')) else 1
    else: i+=1
SRC, OUTB, GLB = O['src'], O['out-blend'], O.get('out-glb')
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']
arm.data.pose_position = 'REST'
bpy.context.view_layer.update()
rep = {}
for side, up in (('L','mixamorig:LeftUpLeg'), ('R','mixamorig:RightUpLeg')):
    pb = arm.pose.bones[up]
    hipW = arm.matrix_world @ pb.head
    kneeW = arm.matrix_world @ pb.tail
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or ob.name.startswith('WGT_'): continue
        if ob.name not in ('DragonMan_Body','DragonMan_Foot.L','DragonMan_Foot.R'): continue
        M = ob.matrix_world
        gi = {g.index: g.name for g in ob.vertex_groups}
        gup = ob.vertex_groups.get(up)
        if not gup: continue
        hipsg = ob.vertex_groups.get('mixamorig:Hips') or ob.vertex_groups.new(name='mixamorig:Hips')
        seg = kneeW - hipW; L2 = seg.length_squared
        n = 0; wmax = 0.0
        for v in ob.data.vertices:
            w = 0.0
            for g in v.groups:
                if gi.get(g.group) == up: w = g.weight
            if w < 0.3: continue
            pw = M @ v.co
            t = (pw - hipW).dot(seg) / L2          # 0 at hip, 1 at knee
            if t > 0.45: continue                  # only the upper thigh
            if t < -0.35: continue
            k = (0.45 - t) / 0.80                  # 0..1 from t=0.45 down to t=-0.35
            hips_w = 0.55 * max(0.0, min(1.0, k))
            if hips_w < 0.02: continue
            hipsg.add([v.index], hips_w, 'REPLACE')
            gup.add([v.index], w * (1.0 - hips_w), 'REPLACE')
            n += 1; wmax = max(wmax, hips_w)
        if n:
            rep[ob.name + '.' + side] = {'verts': n, 'max_hips_w': round(wmax,3)}
print('[TH]', json.dumps(rep))
bpy.ops.wm.save_as_mainfile(filepath=OUTB)
print('[TH] saved', OUTB, 'objects:', list(rep.keys()))
