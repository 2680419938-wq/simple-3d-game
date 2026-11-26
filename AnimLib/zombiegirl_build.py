# Zombiegirl(W Kurniawan, With Skin) → 网页用 GLB：
#   1) 贴图去重、降到 1K   2) 丢掉自带动作
#   3) 把自家 5 条 Mixamo 动作（37 骨，同 mixamorig: 命名）作为 NLA 轨挂到女僵尸骨架上一起烘
# 这样坐标/骨骼轴向的换算全在 Blender 里完成，网页端 GLTFLoader 直接得到可用 clip
import bpy, os, sys

# 源文件不入库（Mixamo 下载的 15.9 MB With Skin FBX）。默认用本机路径，也可以显式给：
#   blender -b --python AnimLib/zombiegirl_build.py -- "D:\某个\角色.fbx"
SRC = next((a for a in sys.argv if a.lower().endswith('.fbx')), r'D:\浏览器·\Zombiegirl W Kurniawan.fbx')
CLIPS = r'D:\ai\建模\web-preview\public\models\zombie'
OUT = r'D:\ai\建模\web-preview\public\models\zombie\zombiegirl.glb'
MAXTEX = 1024
NAMES = ['idle', 'walk', 'run', 'attack', 'death']

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
girl = next(o for o in bpy.data.objects if o.type == 'ARMATURE')

for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
for o in bpy.data.objects:
    if o.animation_data:
        o.animation_data_clear()

keep = {}
for img in list(bpy.data.images):
    key = (img.filepath, tuple(img.size))
    if key in keep and keep[key] is not img:
        keep[key].user_remap(img)
        bpy.data.images.remove(img)
    else:
        keep[key] = img
for img in bpy.data.images:
    if max(img.size) > MAXTEX:
        img.scale(MAXTEX, MAXTEX)
        img.pack()
print('IMG left', [(i.name, tuple(i.size)) for i in bpy.data.images])

girl.animation_data_create()
for ibone in girl.pose.bones:
    ibone.rotation_mode = 'QUATERNION'
for name in NAMES:
    path = os.path.join(CLIPS, name + '.fbx')
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    newobjs = set(bpy.data.objects) - before
    src_arm = next(o for o in newobjs if o.type == 'ARMATURE')
    act = src_arm.animation_data.action
    act.name = name
    act.use_fake_user = True
    missing = [b.name for b in src_arm.pose.bones if b.name not in girl.pose.bones]
    print('CLIP', name, 'frames', tuple(round(x) for x in act.frame_range), 'missingBones', len(missing), 'slots', len(getattr(act, 'slots', [])))
    trk = girl.animation_data.nla_tracks.new()
    trk.name = name
    trk.strips.new(name, int(act.frame_range[0]), act)
    trk.mute = True
    for o in newobjs:
        bpy.data.objects.remove(o, do_unlink=True)

# 丢掉 specular 贴图（KHR_materials_specular，省 1 MB 左右，观感几乎不变）
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    for node in mat.node_tree.nodes:
        if node.type != 'BSDF_PRINCIPLED':
            continue
        for inp in node.inputs:
            if 'Specular' in inp.name or inp.name in ('Sheen Weight', 'Coat Weight'):
                for link in list(inp.links):
                    mat.node_tree.links.remove(link)
print('MATS', [(m.name, len([n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE']) if m.use_nodes else 0) for m in bpy.data.materials])
print('NLA tracks', [t.name for t in girl.animation_data.nla_tracks], 'actions', [a.name for a in bpy.data.actions])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_animation_mode='NLA_TRACKS',
    export_bake_animation=False,
    export_optimize_animation_size=False,
)
print('GLB bytes', os.path.getsize(OUT))
