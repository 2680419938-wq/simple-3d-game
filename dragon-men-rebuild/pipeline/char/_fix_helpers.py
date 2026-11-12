import bpy, bmesh
P=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody/char_rig_flat.blend'
Q=r'D:/ai/建模/dragon-men-rebuild/skin-work/thigh_diag/newbody/char_rig_clean.blend'
GLB=r'D:/ai/建模/dragon-man-final/DragonMan_New.glb'
bpy.ops.wm.open_mainfile(filepath=P)
h=bpy.data.objects['Human']
bad=set()
for g in h.vertex_groups:
    n=g.name.lower()
    if n.startswith('helper') or n=='helpergeometry': bad.add(g.index)
print('BADGROUPS',len(bad))
keep=set()
for v in h.data.vertices:
    if any(gg.group==h.vertex_groups['body'].index for gg in v.groups): keep.add(v.index)
print('KEEP',len(keep),'of',len(h.data.vertices))
bm=bmesh.new(); bm.from_mesh(h.data); bm.verts.ensure_lookup_table()
kill=[v for v in bm.verts if v.index not in keep]
bmesh.ops.delete(bm, geom=kill, context='VERTS')
bm.to_mesh(h.data); bm.free()
print('HUMAN after',len(h.data.vertices),len(h.data.polygons))
for m in list(h.modifiers):
    if m.type=='MASK': h.modifiers.remove(m)
total=0
for o in bpy.data.objects:
    if o.type!='MESH' or o is h: continue
    bi={g.index for g in o.vertex_groups if g.name.lower().startswith('helper') or g.name.lower()=='helpergeometry'}
    if not bi: continue
    kb=set()
    for v in o.data.vertices:
        if any(gg.group in bi for gg in v.groups): kb.add(v.index)
    if not kb: continue
    bm=bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index in kb], context='VERTS')
    bm.to_mesh(o.data); bm.free()
    total+=len(kb)
    for m in list(o.modifiers):
        if m.type=='MASK': o.modifiers.remove(m)
print('SHELL helper verts removed',total)
for o in bpy.data.objects:
    if o.type=='MESH': print('  %-22s v=%d'%(o.name,len(o.data.vertices)))
bpy.ops.wm.save_as_mainfile(filepath=Q)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', export_apply=False, export_animations=True, export_animation_mode='ACTIONS', export_bake_animation=True)
import os; print('GLB',os.path.getsize(GLB))
print('DONE')