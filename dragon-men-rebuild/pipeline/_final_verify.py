# -*- coding: utf-8 -*-
"""Independent acceptance verifier for the 4 deliverable GLBs (pure stdlib, no Blender)."""
import json, struct, os, math, hashlib, sys

OUT = r'D:\ai\建模\dragon-men-rebuild\final'
TARGET = ['root','pelvis','spine','chest','neck','head',
 'shoulder.L','upper_arm.L','forearm.L','hand.L',
 'shoulder.R','upper_arm.R','forearm.R','hand.R',
 'tail.001','tail.002','tail.003','tail.004','tail.005','tail.006',
 'thigh.L','shin.L','foot.L','toe.01.L','toe.02.L','toe.03.L',
 'thigh.R','shin.R','foot.R','toe.01.R','toe.02.R','toe.03.R']
FILES = [('LOD0', 'DragonMan_Game.glb'), ('TPOSE', 'DragonMan_TPose.glb'),
         ('LOD1', 'DragonMan_Game_LOD1.glb'), ('LOD2', 'DragonMan_Game_LOD2.glb')]

CT = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

def load(p):
    b = open(p, 'rb').read()
    total = struct.unpack('<III', b[:12])[2]; off = 12; js = None; bins = []
    while off < total:
        clen, ctype = struct.unpack('<II', b[off:off+8]); off += 8
        c = b[off:off+clen]; off += clen
        if ctype == 0x4E4F534A: js = json.loads(c)
        elif ctype == 0x004E4942: bins.append(c)
    return js, b''.join(bins), len(b)

def acc_read(g, bin_, i):
    a = g['accessors'][i]; n = NC[a['type']]; fmt, sz = CT[a['componentType']]
    bv = g['bufferViews'][a['bufferView']]
    base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = bv.get('byteStride', n * sz)
    return [struct.unpack_from('<' + fmt * n, bin_, base + k * stride) for k in range(a['count'])]

def m_ident(): return [[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]
def m_mul(A, B):
    return [[sum(A[i][k]*B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
def m_trs(n):
    if 'matrix' in n:
        m = n['matrix']
        return [[m[0],m[4],m[8],m[12]],[m[1],m[5],m[9],m[13]],[m[2],m[6],m[10],m[14]],[m[3],m[7],m[11],m[15]]]
    t = n.get('translation', [0.,0.,0.]); q = n.get('rotation', [0.,0.,0.,1.]); s = n.get('scale', [1.,1.,1.])
    x, y, z, w = q
    R = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), 0.],
         [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w), 0.],
         [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y), 0.],
         [0., 0., 0., 1.]]
    for i in range(3):
        for j in range(3): R[i][j] *= s[j]
        R[i][3] = t[i]
    return R
def col(M, j): return [M[0][j], M[1][j], M[2][j]]
def norm(v): 
    L = math.sqrt(sum(x*x for x in v)); return [x/L for x in v] if L > 1e-12 else [0.,0.,0.]

def jpeg_size(d):
    j = 2
    while j < len(d) - 9:
        if d[j] != 0xFF: j += 1; continue
        m = d[j+1]
        if m in (0xC0, 0xC1, 0xC2): 
            h, w = struct.unpack('>HH', d[j+5:j+9]); return w, h
        j += 2 + struct.unpack('>H', d[j+2:j+4])[0]
    return 0, 0

def analyze(tag, fname):
    path = os.path.join(OUT, fname)
    g, bin_, size = load(path)
    rep = {'tag': tag, 'file': fname, 'bytes': size,
           'sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest().upper()}
    nodes = g['nodes']
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get('children', []): parent[c] = i
    cache = {}
    def W(i):
        if i in cache: return cache[i]
        M = m_trs(nodes[i])
        if i in parent: M = m_mul(W(parent[i]), M)
        cache[i] = M; return M
    sk = g['skins'][0]; J = sk['joints']
    names = [nodes[i].get('name') for i in J]
    rep['joint_count'] = len(J)
    rep['joint_names'] = names
    rep['joints_exact_order'] = (names == TARGET)
    rep['joint_order_diff'] = [n for n in TARGET if n not in names]
    pos = {nodes[i].get('name'): [W(i)[0][3], W(i)[1][3], W(i)[2][3]] for i in J}
    rep['joint_world'] = {k: [round(x, 6) for x in v] for k, v in pos.items()}
    # -- T-pose arms (glTF y)
    def ac(side):
        u, f, h = pos['upper_arm.' + side], pos['forearm.' + side], pos['hand.' + side]
        return {'dy_forearm': round(abs(f[1]-u[1]), 6), 'dy_hand': round(abs(h[1]-u[1]), 6),
                'x_upper': round(u[0], 6), 'x_hand': round(h[0], 6)}
    rep['arms'] = {'L': ac('L'), 'R': ac('R')}
    rep['arms_dy_max'] = max([v for s in ('L','R') for k, v in rep['arms'][s].items() if k.startswith('dy')])
    # -- foot bone vs horizontal  (bone node local +Y is the bone axis)
    rep['foot'] = {}
    for side in ('L', 'R'):
        i = next(k for k, n in enumerate(nodes) if n.get('name') == 'foot.' + side)
        d = norm(col(W(i), 1))
        rep['foot'][side] = {'dir': [round(x, 6) for x in d],
                             'angle_deg': round(math.degrees(math.asin(min(1., abs(d[1])))), 4)}
    # -- pivot
    amx = (pos['foot.L'][0] + pos['foot.R'][0]) / 2.0
    amz = (pos['foot.L'][2] + pos['foot.R'][2]) / 2.0
    rep['pivot'] = {'ankle_mid_x': amx, 'ankle_mid_z': amz,
                    'ankle_mid_z_abs': abs(amz), 'ankle_mid_y': (pos['foot.L'][1]+pos['foot.R'][1])/2.0}
    # -- mesh / materials / bbox
    rep['mesh_count'] = len(g.get('meshes', []))
    rep['prim_count'] = [len(m['primitives']) for m in g['meshes']]
    rep['material_count'] = len(g.get('materials', []))
    rep['material_names'] = [m.get('name') for m in g.get('materials', [])]
    reps = []
    mn = [1e30]*3; mx = [-1e30]*3; tcount = 0; vcount = 0
    for pr in g['meshes'][0]['primitives']:
        a = g['accessors'][pr['attributes']['POSITION']]
        tcount += g['accessors'][pr['indices']]['count'] // 3
        vcount += a['count']
        for k in range(3):
            mn[k] = min(mn[k], a['min'][k]); mx[k] = max(mx[k], a['max'][k])
        reps.append({'mat': g['materials'][pr['material']]['name'], 'tris': g['accessors'][pr['indices']]['count']//3})
    rep['triangles'] = tcount; rep['vertices'] = vcount; rep['prims'] = reps
    rep['bbox'] = {'min': [round(x, 6) for x in mn], 'max': [round(x, 6) for x in mx],
                   'height_y': round(mx[1]-mn[1], 6), 'sole_y': round(mn[1], 6),
                   'depth_z': round(mx[2]-mn[2], 6)}
    rep['tail_dir'] = {'tail006_minus_tail001_z': round(pos['tail.006'][2]-pos['tail.001'][2], 5),
                       'tail006_minus_pelvis_z': round(pos['tail.006'][2]-pos['pelvis'][2], 5),
                       'bbox_min_z': round(mn[2], 5)}
    # -- skin weights
    tot_v = 0; max_inf = 0; sum_min = 9.; sum_max = -9.; zero = 0; extra_sets = 0
    for pr in g['meshes'][0]['primitives']:
        at = pr['attributes']
        extra_sets = max(extra_sets, sum(1 for k in at if k.startswith('JOINTS_')))
        JJ = acc_read(g, bin_, at['JOINTS_0']); WW = acc_read(g, bin_, at['WEIGHTS_0'])
        acc = g['accessors'][at['WEIGHTS_0']]
        for jv, wv in zip(JJ, WW):
            ws = [w / 65535.0 if acc['componentType'] == 5123 else w for w in wv]
            nz = [w for w, j in zip(ws, jv) if j > 0 or w > 0]
            tot_v += 1
            max_inf = max(max_inf, len(nz))
            s = sum(ws)
            sum_min = min(sum_min, s); sum_max = max(sum_max, s)
            if s <= 1e-6: zero += 1
    rep['weights'] = {'vertices': tot_v, 'max_influences': max_inf, 'weightset_sets': extra_sets,
                      'sum_min': round(sum_min, 7), 'sum_max': round(sum_max, 7), 'zero_weight_verts': zero}
    # -- images
    bvs = g['bufferViews']; imgs = []
    for im in g.get('images', []):
        bv = bvs[im['bufferView']]
        data = bin_[bv['byteOffset']:bv['byteOffset']+bv['byteLength']]
        w = h = 0; is_jpeg = data[:2] == b'\xff\xd8'
        if is_jpeg: w, h = jpeg_size(data)
        elif data[:8] == b'\x89PNG\r\n\x1a\n': w, h = struct.unpack('>II', data[16:24])
        imgs.append({'name': im.get('name'), 'mime': im.get('mimeType'), 'w': w, 'h': h, 'bytes': bv['byteLength']})
    rep['images'] = imgs
    rep['image_summary'] = {
        'count': len(imgs),
        'all_jpeg': all(i['mime'] == 'image/jpeg' for i in imgs),
        'normal': sorted({i['w'] for i in imgs if 'Normal' in (i['name'] or '')}),
        'other': sorted({i['w'] for i in imgs if 'Normal' not in (i['name'] or '')}),
    }
    # -- animations
    anims = []
    for a in g.get('animations', []):
        tmin = 1e30; tmax = -1e30; keys = 0; paths = set()
        for ch in a['channels']:
            sm = a['samplers'][ch['sampler']]
            t = acc_read(g, bin_, sm['input'])
            tmin = min(tmin, t[0][0]); tmax = max(tmax, t[-1][0]); keys = max(keys, len(t))
            paths.add(ch['target']['path'])
        anims.append({'name': a.get('name'), 'channels': len(a['channels']), 'keys': keys,
                      't_min': round(tmin, 6), 't_max': round(tmax, 6), 'duration': round(tmax - tmin, 6),
                      'paths': sorted(paths)})
    rep['animations'] = anims
    # guard against a flattened (REST-evaluated) sample set
    mo = {'max_rot_span': 0.0, 'max_trans_span': 0.0}
    for a in g.get('animations', []):
        for ch in a['channels']:
            p = ch['target']['path']
            if p not in ('rotation', 'translation'): continue
            vals = acc_read(g, bin_, a['samplers'][ch['sampler']]['output'])
            span = max(max(v[k] for v in vals) - min(v[k] for v in vals) for k in range(len(vals[0])))
            k = 'max_rot_span' if p == 'rotation' else 'max_trans_span'
            mo[k] = max(mo[k], span)
    rep['motion'] = {k: round(v, 6) for k, v in mo.items()}
    # -- bone node TRS contract
    rep['joint_trs'] = [[nodes[i].get('name'), nodes[i].get('translation'), nodes[i].get('rotation'), nodes[i].get('scale')] for i in J]
    rep['scene_roots'] = [(nodes[i].get('name'), {k: v for k, v in nodes[i].items() if k in ('translation','rotation','scale')}) for i in g['scenes'][0]['nodes']]
    rep['nodes_total'] = len(nodes)
    rep['attributes'] = sorted({k for pr in g['meshes'][0]['primitives'] for k in pr['attributes']})
    return rep

def main():
    out = {}
    for tag, fname in FILES:
        out[tag] = analyze(tag, fname)
    # ---- cross-file skeleton contract
    trs = {t: out[t]['joint_trs'] for t in ('LOD0', 'LOD1', 'LOD2')}
    same = trs['LOD0'] == trs['LOD1'] == trs['LOD2']
    same_tp = (out['TPOSE']['joint_trs'] == trs['LOD0'])
    out['_contract'] = {'game_trs_identical': same, 'tpose_trs_identical_to_game': same_tp,
                        'joint_names_identical': all(out[t]['joint_names'] == TARGET for t in out)}

    # ---- print
    for tag, fname in FILES:
        r = out[tag]; L = []
        L.append('================ %s  %s ================' % (tag, fname))
        L.append('size=%d  sha256=%s' % (r['bytes'], r['sha256']))
        L.append('[1] joints=%d  names==TARGET(verbatim, same order)=%s  missing=%s'
                 % (r['joint_count'], r['joints_exact_order'], r['joint_order_diff']))
        L.append('[2] arms  L dy_forearm=%.6f dy_hand=%.6f | R dy_forearm=%.6f dy_hand=%.6f  max=%.6f  (<=0.02)'
                 % (r['arms']['L']['dy_forearm'], r['arms']['L']['dy_hand'],
                    r['arms']['R']['dy_forearm'], r['arms']['R']['dy_hand'], r['arms_dy_max']))
        L.append('    foot  L dir=%s angle=%.4f deg | R dir=%s angle=%.4f deg  (<=5)'
                 % (r['foot']['L']['dir'], r['foot']['L']['angle_deg'], r['foot']['R']['dir'], r['foot']['R']['angle_deg']))
        L.append('[3] ankle_mid  x=%.9f  z=%.9f  |.|max=%.3e  (<=1e-4)  y=%.6f'
                 % (r['pivot']['ankle_mid_x'], r['pivot']['ankle_mid_z'],
                    max(abs(r['pivot']['ankle_mid_x']), r['pivot']['ankle_mid_z_abs']), r['pivot']['ankle_mid_y']))
        L.append('[4] bbox min=%s max=%s  height_y=%.6f sole_y=%.6f depth_z=%.6f  (2.01+-0.06, |sole|<=0.01)'
                 % (r['bbox']['min'], r['bbox']['max'], r['bbox']['height_y'], r['bbox']['sole_y'], r['bbox']['depth_z']))
        L.append('    tail: tail006-tail001 z=%.5f  tail006-pelvis z=%.5f  bbox_min_z=%.5f  (tail toward -Z)'
                 % (r['tail_dir']['tail006_minus_tail001_z'], r['tail_dir']['tail006_minus_pelvis_z'], r['tail_dir']['bbox_min_z']))
        L.append('[5] meshes=%d prims=%s materials=%d %s'
                 % (r['mesh_count'], r['prim_count'], r['material_count'], r['material_names']))
        L.append('[6] triangles=%d  vertices=%d  prims=%s'
                 % (r['triangles'], r['vertices'], [(p['mat'], p['tris']) for p in r['prims']]))
        L.append('[7] animations=%s' % (json.dumps(r['animations'], ensure_ascii=False) if r['animations'] else '[] (empty)'))
        L.append('    motion(not flattened): max_rot_span=%.6f  max_trans_span=%.6f'
                 % (r['motion']['max_rot_span'], r['motion']['max_trans_span']))
        L.append('[8] weights: verts=%d max_infl=%d weight_sets=%d sum=[%.7f..%.7f] zero_weight_verts=%d'
                 % (r['weights']['vertices'], r['weights']['max_influences'], r['weights']['weightset_sets'],
                    r['weights']['sum_min'], r['weights']['sum_max'], r['weights']['zero_weight_verts']))
        s = r['image_summary']
        L.append('[9] images=%d all_jpeg=%s normal_px=%s other_px=%s' % (s['count'], s['all_jpeg'], s['normal'], s['other']))
        L.append('    ' + ', '.join('%s:%dx%d' % (i['name'], i['w'], i['h']) for i in r['images']))
        L.append('    attrs=%s  scene_roots=%s  nodes=%d' % (r['attributes'], r['scene_roots'], r['nodes_total']))
        print('\n'.join(L)); print()
    c = out['_contract']
    print('[10] skeleton contract: game TRS identical=%s | TPOSE TRS identical to game=%s | joint names identical=%s'
          % (c['game_trs_identical'], c['tpose_trs_identical_to_game'], c['joint_names_identical']))

    # ---- pass/fail
    checks = []
    def ok(name, cond, detail):
        checks.append((name, bool(cond), detail))
    for tag, fname in FILES:
        r = out[tag]; n = tag
        ok(n + ' 1 joint count/names', r['joint_count'] == 32 and r['joints_exact_order'], r['joint_count'])
        ok(n + ' 2 T-pose arms dy<=0.02', r['arms_dy_max'] <= 0.02, round(r['arms_dy_max'], 6))
        ok(n + ' 2 foot angle<=5deg', max(r['foot']['L']['angle_deg'], r['foot']['R']['angle_deg']) <= 5.0,
           (r['foot']['L']['angle_deg'], r['foot']['R']['angle_deg']))
        ok(n + ' 3 ankle mid', max(abs(r['pivot']['ankle_mid_x']), r['pivot']['ankle_mid_z_abs']) <= 1e-4,
           (r['pivot']['ankle_mid_x'], r['pivot']['ankle_mid_z']))
        ok(n + ' 4 sole |y|<=0.01', abs(r['bbox']['sole_y']) <= 0.01, r['bbox']['sole_y'])
        ok(n + ' 4 height 2.01+-0.06', abs(r['bbox']['height_y'] - 2.010) <= 0.06, r['bbox']['height_y'])
        ok(n + ' 4 tail toward -Z', r['tail_dir']['tail006_minus_pelvis_z'] < 0, r['tail_dir']['tail006_minus_pelvis_z'])
        ok(n + ' 5 1mesh/4prim/4mat', r['mesh_count'] == 1 and r['prim_count'] == [4] and r['material_count'] == 4,
           (r['mesh_count'], r['prim_count'], r['material_count']))
        ok(n + ' 8 weights', r['weights']['max_influences'] <= 4 and r['weights']['weightset_sets'] == 1
           and r['weights']['zero_weight_verts'] == 0
           and abs(r['weights']['sum_min'] - 1) < 1e-4 and abs(r['weights']['sum_max'] - 1) < 1e-4,
           (r['weights']['max_influences'], r['weights']['zero_weight_verts'], r['weights']['sum_min'], r['weights']['sum_max']))
    ok('LOD0 6 tris 53012+-500', abs(out['LOD0']['triangles'] - 53012) <= 500, out['LOD0']['triangles'])
    ok('LOD1 6 tris 26500+-800', abs(out['LOD1']['triangles'] - 26500) <= 800, out['LOD1']['triangles'])
    ok('LOD2 6 tris 11650+-800', abs(out['LOD2']['triangles'] - 11650) <= 800, out['LOD2']['triangles'])
    ok('TPOSE 7 animations empty', out['TPOSE']['animations'] == [], len(out['TPOSE']['animations']))
    for tag in ('LOD0', 'LOD1', 'LOD2'):
        a = out[tag]['animations']
        ok(tag + ' 7 Idle_Lively 4.00s', len(a) == 1 and a[0]['name'] == 'Idle_Lively' and abs(a[0]['duration'] - 4.0) <= 0.05,
           a)
    for tag in ('LOD0', 'LOD1', 'LOD2'):
        ok(tag + ' 7 animation is not flattened', out[tag]['motion']['max_rot_span'] > 0.01,
           out[tag]['motion'])
    def tex(spec_other, spec_normal, tag):
        s = out[tag]['image_summary']
        good = s['all_jpeg'] and s['other'] == [spec_other] and s['normal'] == [spec_normal]
        ok(tag + ' 9 textures %d/%d jpeg' % (spec_other, spec_normal), good, (s['all_jpeg'], s['other'], s['normal']))
    tex(2048, 1024, 'LOD0'); tex(2048, 1024, 'TPOSE'); tex(1024, 1024, 'LOD1'); tex(512, 512, 'LOD2')
    ok('10 game bone TRS identical', c['game_trs_identical'], c['game_trs_identical'])
    bad = [x for x in checks if not x[1]]
    print()
    print('---- ACCEPTANCE CRITERIA ----')
    for name, good, detail in checks:
        print('%-5s %-34s %s' % ('PASS' if good else 'FAIL', name, detail))
    print()
    print('TOTAL %d checks, %d passed, %d failed' % (len(checks), len(checks) - len(bad), len(bad)))
    for b in bad: print('  FAILED:', b[0], b[2])
    with open(r'D:\ai\建模\.dsh\tmp-final\_final_verify_report.json', 'w', encoding='utf-8') as fh:
        json.dump({'files': out, 'checks': checks}, fh, ensure_ascii=False, indent=1)
    return 0 if not bad else 1

sys.exit(main())
