# -*- coding: utf-8 -*-
# m8: exact GLB-space skinning audit (numpy, no Blender). Per animation frame: min Y of all skinned
# vertices, knee angles, loop delta, bone world translation drift. Also static bbox for each GLB.
import json, struct, sys, os, math
import numpy as np

def load(p):
    b = open(p, 'rb').read(); off = 12; js = None; bn = None
    while off < len(b):
        ln, ty = struct.unpack_from('<II', b, off); off += 8
        ch = b[off:off + ln]; off += ln
        if ty == 0x4E4F534A: js = json.loads(ch.decode('utf-8'))
        elif ty == 0x004E4942: bn = ch
    return js, bn

DT = {5126: np.float32, 5123: np.uint16, 5121: np.uint8, 5125: np.uint32, 5122: np.int16}
NC = {'VEC3': 3, 'VEC4': 4, 'SCALAR': 1, 'MAT4': 16, 'VEC2': 2}

def acc(g, b, i):
    a = g['accessors'][i]; bv = g['bufferViews'][a['bufferView']]
    n = NC[a['type']]; dt = np.dtype(DT[a['componentType']]); it = dt.itemsize * n
    off = bv.get('byteOffset', 0) + a.get('byteOffset', 0); st = bv.get('byteStride', it)
    if st == it:
        return np.frombuffer(b, dtype=dt, count=a['count'] * n, offset=off).reshape(a['count'], n).astype(np.float64)
    rows = [np.frombuffer(b, dtype=dt, count=n, offset=off + k * st) for k in range(a['count'])]
    return np.vstack(rows).astype(np.float64)

def trs(t, r, s):
    x, y, z, w = r
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R * np.array(s); M[:3, 3] = t; return M

def slerp(a, b, u):
    d = float(a @ b)
    if d < 0: b = -b; d = -d
    if d > 0.9995:
        q = a + u * (b - a); return q / np.linalg.norm(q)
    th = math.acos(max(-1.0, min(1.0, d)))
    return (math.sin((1 - u) * th) * a + math.sin(u * th) * b) / math.sin(th)

def sample(ts, vs, t, interp):
    if t <= ts[0]: return vs[0]
    if t >= ts[-1]: return vs[-1]
    i = max(0, min(int(np.searchsorted(ts, t)) - 1, len(ts) - 2))
    u = (t - ts[i]) / (ts[i + 1] - ts[i])
    if interp == 'STEP': return vs[i]
    if vs.shape[1] == 4: return slerp(vs[i], vs[i + 1], u)
    return vs[i] + u * (vs[i + 1] - vs[i])

class M:
    def __init__(self, p):
        self.g, self.bin = load(p); g = self.g
        self.nodes = g['nodes']; self.N = len(self.nodes); self.par = {}
        for i, n in enumerate(self.nodes):
            for c in n.get('children', []): self.par[c] = i
        self.dep = {}
        for i in range(self.N):
            k = 0; j = i
            while j in self.par: j = self.par[j]; k += 1
            self.dep[i] = k
        self.anims = {}
        for a in g.get('animations', []):
            ch = {}
            for c in a['channels']:
                s = a['samplers'][c['sampler']]
                ch.setdefault(c['target']['node'], {})[c['target']['path']] = (
                    acc(g, self.bin, s['input'])[:, 0], acc(g, self.bin, s['output']), s.get('interpolation', 'LINEAR'))
            self.anims[a.get('name', '?')] = ch
        self.skin = g['skins'][0]; self.joints = self.skin['joints']
        self.jnames = [self.nodes[j].get('name') for j in self.joints]
        self.ibm = acc(g, self.bin, self.skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
        self.meshnodes = [i for i, n in enumerate(self.nodes) if 'mesh' in n]

    def world(self, ch=None, t=0.0):
        W = {}
        for i in sorted(range(self.N), key=lambda i: self.dep[i]):
            n = self.nodes[i]
            tr = np.array(n.get('translation', [0, 0, 0]), float)
            ro = np.array(n.get('rotation', [0, 0, 0, 1]), float)
            sc = np.array(n.get('scale', [1, 1, 1]), float)
            if ch and i in ch:
                c = ch[i]
                if 'translation' in c: tr = sample(c['translation'][0], c['translation'][1], t, c['translation'][2])
                if 'rotation' in c: ro = sample(c['rotation'][0], c['rotation'][1], t, c['rotation'][2])
                if 'scale' in c: sc = sample(c['scale'][0], c['scale'][1], t, c['scale'][2])
            Mx = trs(tr, ro, sc)
            W[i] = W[self.par[i]] @ Mx if i in self.par else Mx
        return W

    def verts(self, ch=None, t=0.0):
        W = self.world(ch, t); g = self.g
        pal = np.stack([W[j] @ self.ibm[k] for k, j in enumerate(self.joints)])
        out = []
        for mi in self.meshnodes:
            MW = W[mi]
            for pr in g['meshes'][self.nodes[mi]['mesh']]['primitives']:
                P = acc(g, self.bin, pr['attributes']['POSITION'])
                if 'JOINTS_0' not in pr['attributes']:
                    out.append(P @ MW[:3, :3].T + MW[:3, 3]); continue
                J = acc(g, self.bin, pr['attributes']['JOINTS_0']).astype(int)
                Wt = acc(g, self.bin, pr['attributes']['WEIGHTS_0'])
                v = np.zeros((P.shape[0], 3))
                for k in range(4):
                    Mk = pal[J[:, k]]
                    v += (np.einsum('nij,nj->ni', Mk[:, :3, :3], P) + Mk[:, :3, 3]) * Wt[:, k:k + 1]
                out.append(v)  # glTF: a skinned mesh ignores its node transform; joints already give scene space
        return np.vstack(out)

    def pos(self, W, name):
        i = self.jnames.index(name); return W[self.joints[i]][:3, 3]

def knee(W, m, side):
    U = m.pos(W, 'mixamorig:%sUpLeg' % side); l = m.pos(W, 'mixamorig:%sLeg' % side); f = m.pos(W, 'mixamorig:%sFoot' % side)
    a = l - U; b = f - l
    a /= np.linalg.norm(a); b /= np.linalg.norm(b)
    return math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b)))))

for p in sys.argv[1:]:
    m = M(p); rep = {'file': os.path.basename(p), 'joints': len(m.joints), 'meshnodes': len(m.meshnodes)}
    V0 = m.verts(None, 0.0)
    rep['rest_bbox'] = [[round(float(v), 5) for v in V0.min(0)], [round(float(v), 5) for v in V0.max(0)]]
    for anim, ch in m.anims.items():
        ts = [c['input'] for c in ch.values() if 'input' in c]
        tmax = max(float(c[0][-1]) for paths in ch.values() for c in paths.values())
        ts0 = max(float(c[0][0]) for paths in ch.values() for c in paths.values())
        nkey = max(len(c[0]) for paths in ch.values() for c in paths.values())
        nfr = nkey
        rec = {'t': [round(ts0, 6), round(tmax, 6)], 'duration': round(tmax - ts0, 6), 'keys': nkey,
               'channels': sum(len(v) for v in ch.values()), 'miny': [], 'kneeL': [], 'kneeR': []}
        first = last = None
        for f in range(nfr):
            t = ts0 + (tmax - ts0) * f / (nfr - 1)
            W = m.world(ch, t)
            V = m.verts(ch, t)
            rec['miny'].append(round(float(V[:, 1].min()), 6))
            rec['kneeL'].append(round(knee(W, m, 'Left'), 3)); rec['kneeR'].append(round(knee(W, m, 'Right'), 3))
            if f == 0: first = W
            if f == nfr - 1: last = W
        rec['loop_max_delta'] = round(max(float(np.abs(first[j] - last[j]).max()) for j in m.joints), 9)
        rec['miny_worst'] = min(rec['miny']); rec['miny_argmin'] = rec['miny'].index(min(rec['miny']))
        rec['knee_max'] = [max(rec['kneeL']), max(rec['kneeR'])]
        rec['miny_all_nonneg'] = all(v >= 0 for v in rec['miny'])
        rep[anim] = rec
    print(json.dumps(rep, ensure_ascii=False), flush=True)
