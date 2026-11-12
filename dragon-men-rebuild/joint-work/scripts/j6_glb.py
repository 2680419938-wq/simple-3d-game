# -*- coding: utf-8 -*-
"""j6: parse the exported GLB (joints, tris, materials, images, anim channels, rest-vs-anim)."""
import sys, os, json
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\pipeline')
import numpy as np
from glblib import Model
from check_glb_export import scan_rest_vs_anim

GLB = sys.argv[1] if len(sys.argv) > 1 else r'D:\ai\建模\dragon-men-rebuild\joint-work\DragonMan_Joint_full.glb'
OUT = sys.argv[2] if len(sys.argv) > 2 else r'D:\ai\建模\dragon-men-rebuild\joint-work\verify\glb_verify.json'
m = Model(GLB)
g = m.g
imgs = [i.get('mimeType') for i in g.get('images', [])]
mats = [mt.get('name') for mt in g.get('materials', [])]
anims = {}
for a in g.get('animations', []):
    paths = {}
    tmax = 0.0
    for ch in a['channels']:
        p = ch['target']['path']
        paths[p] = paths.get(p, 0) + 1
        acc_i = a['samplers'][ch['sampler']]['input']
        tmax = max(tmax, float(m.g['accessors'][acc_i].get('max', [0])[0]))
    anims[a.get('name')] = dict(channels=len(a['channels']), paths=paths, tmax=round(tmax, 4),
                               joints=len({ch['target']['node'] for ch in a['channels']}))
bad = scan_rest_vs_anim(m)
nodes = [n.get('name') for n in g.get('nodes', [])]
rep = dict(glb=GLB, bytes=os.path.getsize(GLB), joints=len(m.joints), joint_names=m.jnames,
           tris=int(m.tris), materials=mats, n_materials=len(mats),
           images=imgs, n_images=len(imgs), jpeg_all=bool(imgs) and all(x == 'image/jpeg' for x in imgs),
           anims=anims, rest_vs_anim_bad=[list(map(str, b)) for b in bad],
           node_names=nodes, n_nodes=len(nodes),
           meshes=[me.get('name') for me in g.get('meshes', [])],
           has_skins=len(g.get('skins', [])), skin_joints=[len(s['joints']) for s in g.get('skins', [])])
json.dump(rep, open(OUT, 'w'), indent=1)
print(json.dumps({k: v for k, v in rep.items() if k not in ('joint_names', 'node_names')}, indent=1))
print('joints:', rep['joints'], ' unique:', len(set(m.jnames)))
print('joint_names_head:', m.jnames[:6], '...')
print('rest_vs_anim_bad:', rep['rest_vs_anim_bad'])
