# verify_retarget.py -- compare our baked clip against the source clip bone directions
import bpy, sys, os, json, math
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
SRC, BLEND, CLIP = argv[0], argv[1], argv[2]
REPORT = argv[3] if len(argv) > 3 else None

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
arm.animation_data.action = bpy.data.actions[CLIP]
NF = int(bpy.data.actions[CLIP].frame_range[1])

before = set(o.name for o in bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=SRC, use_anim=True, automatic_bone_orientation=False,
                         ignore_leaf_bones=True, global_scale=1.0)
sarm = max([o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name not in before],
           key=lambda o: len(o.data.bones))

def norm(n):
    s = n.split('|')[-1].replace('mixamorig', '').lower()
    return s.replace(':', '').replace('_', '').replace(' ', '').replace('.00', '').replace('.0', '').replace('.', '')
sb = {norm(b.name): b for b in sarm.data.bones}
db = {norm(b.name): b for b in arm.data.bones}
common = [k for k in db if k in sb]
rows = []
worst = (0.0, None, None)
for i in range(NF):
    sc.frame_set(i + 1)
    for k in common:
        # deformation == world delta (pose * rest^-1); rig-specific bone roll cancels out here
        d = ((arm.matrix_world @ arm.pose.bones[db[k].name].matrix).to_3x3()
             @ (arm.matrix_world @ db[k].matrix_local).to_3x3().inverted()).to_quaternion().to_matrix()
        s = ((sarm.matrix_world @ sarm.pose.bones[sb[k].name].matrix).to_3x3()
             @ (sarm.matrix_world @ sb[k].matrix_local).to_3x3().inverted()).to_quaternion().to_matrix()
        a = math.degrees(d.to_quaternion().rotation_difference(s.to_quaternion()).angle)
        rows.append((i + 1, k, a))
        if a > worst[0]:
            worst = (a, k, i + 1)
per = {}
for f, k, a in rows:
    per.setdefault(k, []).append(a)
rep = {'clip': CLIP, 'frames': NF, 'bones': len(common),
       'max_err_deg': round(worst[0], 3), 'worst_bone': worst[1], 'worst_frame': worst[2],
       'mean_err_deg': round(sum(a for _, _, a in rows) / len(rows), 3),
       'per_bone_max': {k: round(max(v), 2) for k, v in sorted(per.items())}}
print('[VER]', json.dumps(rep['per_bone_max'], ensure_ascii=False))
print('[VER] max', rep['max_err_deg'], 'mean', rep['mean_err_deg'], 'worst', worst[1], worst[2])
if REPORT:
    json.dump(rep, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[VER] DONE')
