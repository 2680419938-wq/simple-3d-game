# -*- coding: utf-8 -*-
# m13: render the deliverable GLBs: T-Pose/A-Pose front+side (rest pose), 3 Walk frames, knee cuff bend 0/90.
import bpy, sys, os, math, json
import numpy as np
from mathutils import Vector, Matrix
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = {argv[i].lstrip('-'): argv[i + 1] for i in range(0, len(argv) - 1, 2)}
OUTDIR = opt['outdir']; os.makedirs(OUTDIR, exist_ok=True)
INFO = {}
def setup_world():
    w = bpy.data.worlds.new('W'); bpy.context.scene.world = w
    w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.11, 0.12, 0.14, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
def add_lights(fwd, lat):
    for name, d, e in (('key', (fwd + Vector((0, 0, 0.6)) + lat * 0.3).normalized(), 4.0),
                       ('fill', (-fwd + Vector((0, 0, 0.3)) - lat * 0.4).normalized(), 1.6),
                       ('rim', (lat + Vector((0, 0, 0.5))).normalized(), 2.2)):
        ld = bpy.data.lights.new(name, 'SUN'); ld.energy = e; ld.angle = math.radians(15)
        ob = bpy.data.objects.new(name, ld); bpy.context.scene.collection.objects.link(ob)
        ob.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
def newcam():
    cd = bpy.data.cameras.new('C'); ob = bpy.data.objects.new('C', cd)
    bpy.context.scene.collection.objects.link(ob); return ob
def render(cam, target, path, scale, res):
    sc = bpy.context.scene; sc.camera = cam
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = path
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = scale
    try: sc.render.engine = 'BLENDER_EEVEE_NEXT'
    except Exception: sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 24
    bpy.ops.render.render(write_still=True)
    print('[M13] rendered', path, os.path.getsize(path))
def load(glb, static):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene; s.render.fps, s.render.fps_base = 30, 1.0
    bpy.ops.import_scene.gltf(filepath=glb)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    if static:
        arm.animation_data_clear()
        for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
    setup_world()
    def P(n): return arm.matrix_world @ arm.pose.bones[n].head
    hips = P('mixamorig:Hips')
    lat = (P('mixamorig:LeftUpLeg') - P('mixamorig:RightUpLeg')); lat.z = 0; lat.normalize()
    fb = arm.matrix_world @ arm.pose.bones['mixamorig:LeftFoot'].head
    tb = arm.matrix_world @ arm.pose.bones['mixamorig:LeftFoot'].tail
    fwd = (tb - fb); fwd.z = 0; fwd.normalize()
    add_lights(fwd, lat)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    dg = bpy.context.evaluated_depsgraph_get(); lo = [9e9] * 3; hi = [-9e9] * 3
    for ob in meshes:
        ev = ob.evaluated_get(dg); me = ev.to_mesh()
        n = len(me.vertices); co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(n, 3)
        MW = np.array(ev.matrix_world); co = co @ MW[:3, :3].T + MW[:3, 3]
        lo = [min(lo[k], float(co[:, k].min())) for k in range(3)]
        hi = [max(hi[k], float(co[:, k].max())) for k in range(3)]
        ev.to_mesh_clear()
    return arm, meshes, fwd, lat, hips, lo, hi

def fullbody(glb, tag, static, frames=None):
    arm, meshes, fwd, lat, hips, lo, hi = load(glb, static)
    INFO[tag] = {'glb': glb, 'bbox': [lo, hi], 'fwd': list(fwd), 'lat': list(lat), 'hips': list(hips)}
    target = Vector((hips.x, hips.y, 1.0))
    cam = newcam()
    if frames:
        for f in frames:
            bpy.context.scene.frame_set(0); bpy.context.scene.frame_set(f)
            bpy.context.view_layer.update()
            cam.location = target + lat * 6
            render(cam, target, os.path.join(OUTDIR, '%s_side_f%02d.png' % (tag, f)), 2.35, (900, 1200))
    else:
        for nm, d, sc, res in (('front', fwd, 3.40, (1200, 1100)), ('side', lat, 2.35, (900, 1200))):
            cam.location = target + d * 6
            render(cam, target, os.path.join(OUTDIR, '%s_%s.png' % (tag, nm)), sc, res)
    return arm, lat

arm, lat = fullbody(opt['tpose'], 'tpose', True)
knee = arm.matrix_world @ arm.pose.bones['mixamorig:LeftLeg'].head
target = knee + Vector((0, 0, -0.03))
kcam = newcam()
kcam.location = knee + lat * 2.0 + Vector((0, 0, 0.02))
render(kcam, target, os.path.join(OUTDIR, 'knee_cuff_bend0.png'), 1.00, (1000, 1000))
pb = arm.pose.bones['mixamorig:LeftLeg']; head = pb.matrix.translation.copy()
pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(math.radians(90), 4, lat) @ Matrix.Translation(-head) @ pb.matrix
bpy.context.view_layer.update()
print('[M13] knee bent, new left-ankle z', float((arm.matrix_world @ arm.pose.bones['mixamorig:LeftFoot'].head).z))
render(kcam, target, os.path.join(OUTDIR, 'knee_cuff_bend90.png'), 1.00, (1000, 1000))
fullbody(opt['apose'], 'apose', True)
fullbody(opt['walk'], 'walk', False, frames=(0, 10, 21))
json.dump(INFO, open(opt['report'], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[M13] DONE')
