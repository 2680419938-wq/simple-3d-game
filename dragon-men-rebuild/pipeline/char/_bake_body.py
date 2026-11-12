import bpy
P=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody/char_rig.blend'
TEX=r'D:/ai/建模/dragon-man-final/tex_body_scale.png'
bpy.ops.wm.open_mainfile(filepath=P)
h=bpy.data.objects['Human']
for o in bpy.context.selected_objects: o.select_set(False)
h.select_set(True); bpy.context.view_layer.objects.active=h
mat=bpy.data.materials['DragonScale']; nt=mat.node_tree
img=bpy.data.images.new('BodyScaleBake', 1024, 1024, alpha=False)
tn=nt.nodes.new('ShaderNodeTexImage'); tn.image=img; tn.location=(-900,400); nt.nodes.active=tn
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=1; sc.cycles.device='CPU'
sc.render.bake.use_pass_direct=False; sc.render.bake.use_pass_indirect=False; sc.render.bake.use_pass_color=True
sc.render.bake.margin=8
bpy.ops.object.bake(type='DIFFUSE')
img.filepath_raw=TEX; img.file_format='PNG'; img.save()
bsdf=[n for n in nt.nodes if n.type=='BSDF_PRINCIPLED'][0]
nt.links.new(tn.outputs['Color'], bsdf.inputs['Base Color'])
print('baked', TEX)
bpy.ops.wm.save_as_mainfile(filepath=P)
print('DONE')