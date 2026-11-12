import bpy, os, math
from mathutils import Vector, Euler
bpy.ops.wm.open_mainfile(filepath=r"D:\ai\建模\AnimLib\out\DragonMan_Std_RunTest.blend")
sc = bpy.context.scene
arm = bpy.data.objects['DragonMan_Rig']
arm.animation_data.action = bpy.data.actions['RunTest']
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 720, 900
sc.render.film_transparent = False
w = bpy.data.worlds.new("W"); sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.06, 0.08, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
cam_data = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cam_data)
sc.collection.objects.link(cam); sc.camera = cam
cam.location = (2.6, -3.4, 1.6)
tgt = Vector((0, 0, 0.95))
d = tgt - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam_data.lens = 55
sun = bpy.data.objects.new("S", bpy.data.lights.new("S", 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 4.0; sun.rotation_euler = Euler((math.radians(55), 0, math.radians(35)))
os.makedirs(r"D:\ai\建模\AnimLib\out\renders", exist_ok=True)
for f in (1, 5, 9, 13, 17):
    sc.frame_set(f)
    sc.render.filepath = r"D:\ai\建模\AnimLib\out\renders\run_%02d.png" % f
    bpy.ops.render.render(write_still=True)
print("RENDERED")
