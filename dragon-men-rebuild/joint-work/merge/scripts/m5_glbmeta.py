# -*- coding: utf-8 -*-
# m5_glbmeta.py: one GLB metadata pass = structure (m5) + node-space pose (m6) + rest-vs-anim/bind (m7).
import json, struct, sys, os, math, collections
import numpy as np
PIPE = r'D:\ai\建模\dragon-men-rebuild\pipeline'
sys.path.insert(0, PIPE)
from glblib import Model
from check_glb_export import scan_rest_vs_anim


def read_glb(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'glTF', path
    off = 12; js = None; bins = None
    while off < len(d):
        ln, ty = struct.unpack_from('<II', d, off); off += 8
        chunk = d[off:off + ln]; off += ln
        if ty == 0x4E4F534A: js = json.loads(chunk.decode('utf-8'))
        elif ty == 0x004E4942: bins = chunk
    return js, bins, len(d)


def structure(path):
    j, b, sz = read_glb(path)
    names = [n.get('name', '?') for n in j['nodes']]
    sk = j.get('skins', [])
    joints = [names[i] for i in sk[0]['joints']] if sk else []
    tris = 0; prims = 0; mats = set(); attrs = collections.Counter()
    for m in j.get('meshes', []):
        for p in m['primitives']:
            prims += 1
            if 'indices' in p: tris += j['accessors'][p['indices']]['count'] // 3
            else: tris += j['accessors'][p['attributes']['POSITION']]['count'] // 3
            if 'material' in p: mats.add(j['materials'][p['material']].get('name', '?'))
            for k in p['attributes']: attrs[k] += 1
    imgs = j.get('images', [])
    mimes = collections.Counter(i.get('mimeType', '?') for i in imgs)
    anims = []
    for a in j.get('animations', []):
        tmax = 0.0; tmin = 9e9
        for s in a['samplers']:
            acc = j['accessors'][s['input']]
            tmin = min(tmin, acc['min'][0]); tmax = max(tmax, acc['max'][0])
        tg = collections.Counter()
        for c in a['channels']: tg[c['target']['path']] += 1
        nb = len(set(c['target']['node'] for c in a['channels']))
        anims.append({'name': a.get('name', '?'), 'channels': len(a['channels']), 'bones': nb,
                      'paths': dict(tg), 't': [round(tmin, 5), round(tmax, 5)],
                      'dur': round(tmax - tmin, 5),
                      'keys': max(j['accessors'][s['input']]['count'] for s in a['samplers'])})
    pos = []
    for m in j.get('meshes', []):
        for p in m['primitives']:
            acc = j['accessors'][p['attributes']['POSITION']]
            if 'min' in acc: pos.append((acc['min'], acc['max']))
    return {'file': os.path.basename(path), 'bytes': sz, 'nodes': len(names), 'meshes': len(j.get('meshes', [])),
            'primitives': prims, 'tris': tris, 'skins': len(sk), 'joints': len(joints),
            'joint_names_ok': all(n.startswith('mixamorig:') for n in joints),
            'materials': sorted(mats), 'n_mat': len(j.get('materials', [])),
            'images': len(imgs), 'mime': dict(mimes), 'attrs': dict(attrs), 'anims': anims,
            'bbox': [round(min(p[0][k] for p in pos), 4) for k in range(3)],
            'bbox_max': [round(max(p[1][k] for p in pos), 4) for k in range(3)]}


def node_mat(n):
    if 'matrix' in n:
        m = n['matrix']; return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    t = n.get('translation', [0, 0, 0]); q = n.get('rotation', [0, 0, 0, 1]); s = n.get('scale', [1, 1, 1])
    x, y, z, w = q
    rr = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
          [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
          [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[rr[r][c] * s[c] for c in range(3)] + [t[r]] for r in range(3)] + [[0, 0, 0, 1]]


def mmul(A, B):
    return [[sum(A[r][k] * B[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def pose(path):
    j, b, sz = read_glb(path)
    names = [n.get('name', '?') for n in j['nodes']]
    par = {}
    for i, n in enumerate(j['nodes']):
        for c in n.get('children', []): par[c] = i
    W = {}
    def world(i):
        if i in W: return W[i]
        M = node_mat(j['nodes'][i])
        if i in par: M = mmul(world(par[i]), M)
        W[i] = M; return M
    idx = {n: i for i, n in enumerate(names)}
    pos = {n: [round(world(idx[n])[r][3], 5) for r in range(3)] for n in names}
    def d(a, b):
        v = [pos[b][k] - pos[a][k] for k in range(3)]; L = math.sqrt(sum(x * x for x in v))
        return [round(x / L, 5) for x in v], L
    out = {'file': os.path.basename(path)}
    for side in ('Left', 'Right'):
        dv, ln = d('mixamorig:%sArm' % side, 'mixamorig:%sForeArm' % side)
        out['arm_' + side] = {'dir': dv, 'len': round(ln, 4),
                              'deg_from_vert': round(math.degrees(math.acos(min(1, abs(dv[1])))), 3),
                              'deg_from_horiz': round(math.degrees(math.acos(min(1, abs(dv[0])))), 3)}
        out['ankle_' + side] = pos['mixamorig:%sFoot' % side]
    out['head'] = pos['mixamorig:Head']; out['hips'] = pos['mixamorig:Hips']
    out['root'] = pos['mixamorig:Root']
    return out


def restanim(path):
    m = Model(path)
    bad = scan_rest_vs_anim(m)
    worst = {'t': 0.0, 'r': 0.0, 's': 0.0}
    for anim, ch in m.anims.items():
        for jn, paths in ch.items():
            n = m.nodes[jn]
            if 'translation' in paths:
                worst['t'] = max(worst['t'], float(np.abs(paths['translation'][1][0] - np.array(n.get('translation', [0, 0, 0]))).max()))
            if 'rotation' in paths:
                q = paths['rotation'][1][0]; r = np.array(n.get('rotation', [0, 0, 0, 1]))
                worst['r'] = max(worst['r'], float(min(np.abs(q - r).max(), np.abs(q + r).max())))
            if 'scale' in paths:
                worst['s'] = max(worst['s'], float(np.abs(paths['scale'][1][0] - np.array(n.get('scale', [1, 1, 1]))).max()))
    W = m.world(None, 0.0)
    dev = 0.0
    for k, jn in enumerate(m.joints):
        M = W[jn] @ m.ibm[k]
        dev = max(dev, float(np.abs(M - np.eye(4)).max()))
    return {'file': os.path.basename(path), 'joints': len(m.joints), 'tris': m.tris,
            'anims': list(m.anims), 'rest_vs_anim_bad': [[str(x) for x in bb] for bb in bad],
            'worst_delta_first_key': {k: round(v, 9) for k, v in worst.items()},
            'rest_world_x_ibm_maxdev': round(dev, 8)}


for p in sys.argv[1:]:
    print('STRUCT ' + json.dumps(structure(p), ensure_ascii=False))
    print('POSE   ' + json.dumps(pose(p), ensure_ascii=False))
    print('RESTAN ' + json.dumps(restanim(p), ensure_ascii=False))
