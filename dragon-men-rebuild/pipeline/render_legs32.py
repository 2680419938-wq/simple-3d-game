# -*- coding: utf-8 -*-
"""Leg close-ups of a shipped GLB: tight ortho on the knees, several azimuths.

Usage: blender.exe -b --factory-startup -P render_legs32.py -- <glb> <outdir> <prefix> <frames csv> <views csv> [res] [samples]
Frames are Blender frames (GLB f1 == Blender 0). Views: outL outR fwd back q34L q34R side.
"""
import bpy, os, math, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
GLB = argv[0]; OUT = argv[1]; PREFIX = '' if argv[2] == '-' else argv[2]
FRAMES = [int(x) for x in argv[3].split(',')]
VIEWS = argv[4].split(',')
RES = int(argv[5]) if len(argv) > 5 else 800
SAMPLES = int(argv[6]) if len(argv) > 6 else 16
ONLY = argv[7].split(',') if len(argv) > 7 else None
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps, sc.render.fps_base = 30, 1.0
bpy.ops.import_scene.gltf(filepath=GLB)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('DragonMan'))
if arm.animation_data is None:
    arm.animation_data_create()

# Blender world after glTF import: +Z up, -Y forward; the leg pair axis is 25 deg off +X
LAT = Vector((0.906, 0.423, 0.0)).normalized()
FWD = Vector((0.0, -1.0, 0.0))
DIRS = {
    'outL': LAT, 'outR': -LAT,
    'fwd': FWD, 'back': -FWD,
    'q34L': (LAT * 0.72 + FWD * 0.69).normalized(),
    'q34R': (-LAT * 0.72 + FWD * 0.69).normalized(),
    'side': Vector((1.0, 0.0, 0.0)),
    'body': LAT,
}
# per-view framing overrides: (target point, ortho width)
VIEWCFG = {'body': (Vector((0.0, 0.0, 1.00)), 2.60)}
# knees sit near z 0.15..0.35; frame the leg pair tightly
ctr = Vector((0.0, 0.0, 0.28))

sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = RES
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True; nt = w.node_tree
bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs[0].default_value = (0.42, 0.45, 0.52, 1); bg.inputs[1].default_value = 1.5
ow = nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(bg.outputs[0], ow.inputs[0])
cd = bpy.data.cameras.new('C'); cd.type = 'ORTHO'; cd.ortho_scale = 0.80
cam = bpy.data.objects.new('C', cd); sc.collection.objects.link(cam); sc.camera = cam
sd = bpy.data.lights.new('S', 'SUN'); sd.energy = 5.5; sd.angle = 0.12
sun = bpy.data.objects.new('S', sd); sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(52), 0, math.radians(38))
fd = bpy.data.lights.new('F', 'SUN'); fd.energy = 1.5; fd.angle = 0.5
fill = bpy.data.objects.new('F', fd); sc.collection.objects.link(fill)
fill.rotation_euler = (math.radians(70), 0, math.radians(-120))

def shot(path, view):
    tgt, osc = VIEWCFG.get(view, (ctr, 0.80))
    cd.ortho_scale = osc
    d = DIRS[view].normalized()
    cam.location = tgt + d * 2.0
    cam.rotation_euler = (tgt - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[R] wrote %s' % os.path.basename(path), flush=True)

acts = {a.name: a for a in bpy.data.actions}
for actname in acts:
    if ONLY and actname not in ONLY: continue
    arm.animation_data.action = acts[actname]
    tag = 'walk' if actname == 'Walk' else 'idle'
    frames = FRAMES if actname == 'Walk' else [0]
    for f in frames:
        sc.frame_set(0); sc.frame_set(f)
        bpy.context.view_layer.update()
        for v in VIEWS:
            shot(os.path.join(OUT, '%s%s_f%02d_%s.png' % (PREFIX, tag, f + 1, v)), v)
print('[R] LEGS DONE', OUT, flush=True)