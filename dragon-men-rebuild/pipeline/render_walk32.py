# -*- coding: utf-8 -*-
"""Render a shipped GLB for gait review: Walk f1/f9/f17/f25/f33 + Idle f1, side + front.

Usage: blender.exe -b --factory-startup -P render_walk32.py -- [glb] [outdir] [walk|idle]

The GLB stores seconds; at 30 fps the source frames 1..33 land on Blender 0..32, so the brief's
"f1..f33" is Blender frame 0/8/16/24/32 (confirmed from the imported action frame_range).
Facing is the rig convention (+Z in glTF = -Y after import), not the splayed feet.
"""
import bpy, os, math, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
GLB = argv[0] if len(argv) > 0 else r'D:\ai\建模\dragon-men-game-walk\DragonMan_Game.glb'
OUT = argv[1] if len(argv) > 1 else r'D:\ai\建模\dragon-men-game-walk\renders'
MODE = argv[2] if len(argv) > 2 else 'walk'
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)   # no default cube/camera/light to confuse the bbox
sc = bpy.context.scene
sc.render.fps, sc.render.fps_base = 30, 1.0
bpy.ops.import_scene.gltf(filepath=GLB)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('DragonMan'))
print('[R] glb=%s armature=%s mesh=%s(%d verts) actions=%s'
      % (os.path.basename(GLB), arm.name, mesh.name, len(mesh.data.vertices),
         [(a.name, tuple(round(x, 1) for x in a.frame_range)) for a in bpy.data.actions]), flush=True)
if arm.animation_data is None:
    arm.animation_data_create()

fwd = Vector((0.0, -1.0, 0.0))      # rig facing after glTF import
side = Vector((1.0, 0.0, 0.0))

V = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
mn = Vector((min(v.x for v in V), min(v.y for v in V), min(v.z for v in V)))
mx = Vector((max(v.x for v in V), max(v.y for v in V), max(v.z for v in V)))
ctr = (mn + mx) / 2.0
print('[R] bbox min=%s max=%s (height %.4f, y-span %.4f)'
      % ([round(x, 4) for x in mn], [round(x, 4) for x in mx], mx.z - mn.z, mx.y - mn.y), flush=True)

bpy.ops.mesh.primitive_plane_add(size=40, location=(ctr.x, ctr.y, 0.0))
fl = bpy.context.object; fl.name = 'FLOOR'
m = bpy.data.materials.new('FLOOR'); m.use_nodes = True
b = m.node_tree.nodes['Principled BSDF']
b.inputs['Base Color'].default_value = (0.18, 0.18, 0.20, 1); b.inputs['Roughness'].default_value = 0.85
fl.data.materials.append(m)
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 32; sc.cycles.use_denoising = True
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True; nt = w.node_tree
bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs[0].default_value = (0.42, 0.45, 0.52, 1); bg.inputs[1].default_value = 1.5
ow = nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(bg.outputs[0], ow.inputs[0])
cd = bpy.data.cameras.new('C'); cd.type = 'ORTHO'
cam = bpy.data.objects.new('C', cd); sc.collection.objects.link(cam); sc.camera = cam
sd = bpy.data.lights.new('S', 'SUN'); sd.energy = 5.5; sd.angle = 0.12
sun = bpy.data.objects.new('S', sd); sc.collection.objects.link(sun); sun.rotation_euler = (math.radians(52), 0, math.radians(38))
fd = bpy.data.lights.new('F', 'SUN'); fd.energy = 1.5; fd.angle = 0.5
fill = bpy.data.objects.new('F', fd); sc.collection.objects.link(fill); fill.rotation_euler = (math.radians(70), 0, math.radians(-120))

# A slight downward tilt keeps the floor readable while staying an orthographic elevation.
TILT = 0.9
VIEWS = {
    'side':  dict(dir=side, res=(1600, 900), ortho=max((mx.y - mn.y), (mx.x - mn.x)) * 1.06),
    'front': dict(dir=fwd,  res=(900, 1100), ortho=max((mx.x - mn.x) * 1.06, (mx.z - mn.z) * 1.06 * 1100.0 / 900.0)),
}

def shot(path, view):
    v = VIEWS[view]
    d = v['dir'].normalized()
    sc.render.resolution_x, sc.render.resolution_y = v['res']
    cam.data.ortho_scale = v['ortho']
    aim = ctr - Vector((0.0, 0.0, 0.25))
    cam.location = ctr + Vector((0.0, 0.0, TILT)) + d * 12.0
    cam.rotation_euler = (aim - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[R] wrote %s (ortho %.3f, %dx%d)' % (os.path.basename(path), v['ortho'], v['res'][0], v['res'][1]), flush=True)

def play(act, frames, tag):
    arm.animation_data.action = bpy.data.actions[act]
    for label, f in frames:
        sc.frame_set(0); sc.frame_set(f)     # step away first: re-setting the same frame is a no-op
        bpy.context.view_layer.update()
        for view in ('side', 'front'):
            shot(os.path.join(OUT, '%s_f%02d_%s.png' % (tag, label, view)), view)

if MODE == 'walk':
    play('Walk', [(1, 0), (9, 8), (17, 16), (25, 24), (33, 32)], 'walk')   # GLB frames are 0-based
play('Idle_Lively', [(1, 0)], 'idle')
print('[R] RENDER DONE mode=%s out=%s' % (MODE, OUT), flush=True)
