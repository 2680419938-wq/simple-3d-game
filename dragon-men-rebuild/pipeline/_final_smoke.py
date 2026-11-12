# -*- coding: utf-8 -*-
"""Criterion 11: load each GLB with the Blender glTF importer; render LOD/TPose views."""
import bpy, os, json, math, sys, traceback
from mathutils import Vector

OUT = r'D:\ai\建模\dragon-men-rebuild\final'
WORK = r'D:\ai\建模\.dsh\tmp-final'
FILES = [('LOD0', 'DragonMan_Game.glb'), ('LOD1', 'DragonMan_Game_LOD1.glb'),
         ('LOD2', 'DragonMan_Game_LOD2.glb'), ('TPOSE', 'DragonMan_TPose.glb')]
res = {}

def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    r = bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    return str(r)

for tag, fname in FILES:
    rec = {}
    try:
        rec['op_result'] = load(os.path.join(OUT, fname))
        arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
        mshs = [o for o in bpy.data.objects if o.type == 'MESH']
        rec['objects'] = len(bpy.data.objects)
        rec['armatures'] = [(o.name, len(o.data.bones)) for o in arms]
        rec['meshes'] = [(o.name, len(o.data.vertices)) for o in mshs]
        tri = 0
        for o in mshs:
            o.data.calc_loop_triangles(); tri += len(o.data.loop_triangles)
        rec['triangles'] = tri
        rec['materials'] = sorted({m.name for o in mshs for m in o.data.materials if m})
        rec['images'] = len(bpy.data.images)
        rec['actions'] = [(a.name, [round(x, 3) for x in a.frame_range]) for a in bpy.data.actions]
        rec['arms_bones_sorted_ok'] = bool(arms) and len(arms[0].data.bones) == 32
        rec['ok'] = True
    except Exception:
        rec['ok'] = False; rec['traceback'] = traceback.format_exc()
    res[tag] = rec
    print('[SMOKE]', tag, json.dumps({k: v for k, v in rec.items() if k != 'traceback'}, ensure_ascii=False))

    if rec['ok'] and mshs:
        # render a 3/4 view (cycles CPU, same camera for every file)
        sc = bpy.context.scene
        tgt = bpy.data.objects.new('tgt', None); sc.collection.objects.link(tgt); tgt.location = (0, 0, 1.0)
        cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd)
        sc.collection.objects.link(cam); sc.camera = cam
        cam.location = (2.6, -4.2, 1.75); cd.lens = 55
        c = cam.constraints.new('TRACK_TO'); c.target = tgt
        c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
        for i, loc in enumerate([(4.0, -4.0, 5.0), (-4.0, -3.0, 2.0), (0.0, 5.0, 2.5)]):
            ld = bpy.data.lights.new('sun%d' % i, 'SUN'); ld.energy = 3.0
            lo = bpy.data.objects.new('sun%d' % i, ld); sc.collection.objects.link(lo)
            lo.location = loc
            c2 = lo.constraints.new('TRACK_TO'); c2.target = tgt
            c2.track_axis = 'TRACK_NEGATIVE_Z'; c2.up_axis = 'UP_Y'
        w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
        bg = w.node_tree.nodes['Background']
        bg.inputs[0].default_value = (0.30, 0.32, 0.36, 1); bg.inputs[1].default_value = 1.2
        sc.render.engine = 'CYCLES'; sc.cycles.samples = 16
        sc.cycles.use_denoising = False; sc.cycles.device = 'CPU'
        sc.render.resolution_x = 620; sc.render.resolution_y = 820
        sc.render.image_settings.file_format = 'PNG'
        sc.render.filepath = os.path.join(WORK, 'render_%s.png' % tag)
        sc.frame_set(1)
        bpy.ops.render.render(write_still=True)
        rec['render'] = sc.render.filepath
        print('[RENDER]', tag, sc.render.filepath)

with open(os.path.join(WORK, '_final_smoke_report.json'), 'w', encoding='utf-8') as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1)
print('SMOKE DONE')
