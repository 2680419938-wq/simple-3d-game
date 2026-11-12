
# -*- coding: utf-8 -*-
"""ac4: GLB acceptance — joints/materials/images/tris/anims + rest-vs-anim (check_glb_export convention)."""
import json, os, sys, struct, hashlib
import numpy as np
sys.path.insert(0, r'D:\ai\建模\dragon-men-rebuild\pipeline')
from glblib import Model
from check_glb_export import scan_rest_vs_anim

NEW = r'D:\ai\建模\dragon-men-rebuild\hand-work\DragonMan_Hands_joint.glb'
REF = r'D:\ai\建模\dragon-men-rebuild\hand-work\ark\src_ref.glb'
OUT = r'D:\ai\建模\dragon-men-rebuild\hand-work\verify\glb_verify.json'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def parse(p):
    b = open(p, 'rb').read()
    off = 12
    g = None
    while off < len(b):
        clen, ctype = struct.unpack('<II', b[off:off + 8])
        off += 8
        chunk = b[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:
            g = json.loads(chunk)
    tris = 0
    prims = 0
    for m in g.get('meshes', []):
        for pr in m['primitives']:
            prims += 1
            tris += g['accessors'][pr['indices']]['count'] // 3
    imgs = [g['images'][i] for i in range(len(g.get('images', [])))]
    mimes = {}
    for im in imgs:
        mimes[im.get('mimeType', '?')] = mimes.get(im.get('mimeType', '?'), 0) + 1
    imbytes = 0
    for im in imgs:
        bv = im.get('bufferView')
        if bv is not None:
            imbytes += g['bufferViews'][bv]['byteLength']
    anims = {}
    for a in g.get('animations', []):
        paths = {}
        for c in a['channels']:
            paths[c['target']['path']] = paths.get(c['target']['path'], 0) + 1
        anims[a.get('name', '?')] = dict(channels=len(a['channels']), samplers=len(a['samplers']), paths=paths)
    skins = [dict(njoints=len(s['joints']),
                  names=[g['nodes'][j].get('name') for j in s['joints']]) for s in g.get('skins', [])]
    meshnames = [n.get('name') for n in g['nodes'] if 'mesh' in n]
    return dict(file=os.path.basename(p), bytes=len(b), sha256=sha(p), tris=tris, prims=prims,
                meshes=len(g.get('meshes', [])), mesh_nodes=meshnames, materials=[m.get('name') for m in g.get('materials', [])],
                images=dict(count=len(imgs), mimes=mimes, bytes=imbytes), skins=skins,
                anims=anims, nodes=len(g['nodes']))


def rva(p):
    m = Model(p)
    bad = scan_rest_vs_anim(m)
    return dict(anim_seen=list(m.anims.keys()), joints=len(m.joints), tris_body=m.tris,
                rest_vs_anim_bad=[[str(x) for x in b] for b in bad])


res = {}
for tag, p in (('src_ref', REF), ('built', NEW)):
    if not os.path.exists(p):
        print('[G] MISSING', p)
        continue
    d = parse(p)
    d.update(rva(p))
    res[tag] = d
    print('[G] %-8s %-28s %7.2f MB tris=%d prims=%d joints=%s mats=%d imgs=%s(%s bytes) anims=%s' %
          (tag, d['file'], d['bytes'] / 1e6, d['tris'], d['prims'],
           [s['njoints'] for s in d['skins']], len(d['materials']), d['images']['count'],
           d['images']['bytes'], {k: v['channels'] for k, v in d['anims'].items()}))
    print('         rest_vs_anim bad:', d['rest_vs_anim_bad'])
    print('         mesh_nodes', d['mesh_nodes'], 'materials', d['materials'])
    print('         mimes', d['images']['mimes'], 'uv?', )

if 'built' in res and 'src_ref' in res:
    a, b = res['src_ref'], res['built']
    print('[G] joints  src %s -> built %s  (unique set equal: %s)' % (
        [s['njoints'] for s in a['skins']], [s['njoints'] for s in b['skins']],
        [sorted(s['names']) for s in a['skins']] == [sorted(s['names']) for s in b['skins']]))
    print('[G] tris src %d -> built %d (+%d)' % (a['tris'], b['tris'], b['tris'] - a['tris']))
    print('[G] anims src %s -> built %s' % ({k: v['channels'] for k, v in a['anims'].items()},
                                            {k: v['channels'] for k, v in b['anims'].items()}))
    print('[G] materials %d -> %d ; images %s -> %s' % (len(a['materials']), len(b['materials']),
                                                        a['images']['mimes'], b['images']['mimes']))
    res['delta'] = dict(tris=b['tris'] - a['tris'], joints_equal=[sorted(s['names']) for s in a['skins']] == [sorted(s['names']) for s in b['skins']],
                        anims_equal={k: v['channels'] for k, v in a['anims'].items()} == {k: v['channels'] for k, v in b['anims'].items()},
                        mats_equal=len(a['materials']) == len(b['materials']))
json.dump(res, open(OUT, 'w'), indent=1)
print('[G] DONE ->', OUT)
