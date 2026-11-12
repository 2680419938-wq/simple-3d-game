# -*- coding: utf-8 -*-
# m12: per-vertex-group face counts (fingers / joint sleeves must not shrink) + plate island audit.
import bpy, sys, json, collections
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = {argv[i].lstrip('-'): argv[i + 1] for i in range(0, len(argv) - 1, 2)}
OUT = opt['report']; R = {}
def dom_faces(ob):
    me = ob.data; gn = [g.name for g in ob.vertex_groups]
    dom = []
    for v in me.vertices:
        gs = v.groups
        dom.append(gn[max(gs, key=lambda g: g.weight).group] if gs else '?')
    cnt = collections.Counter()
    for p in me.polygons:
        c = collections.Counter(dom[i] for i in p.vertices)
        cnt[c.most_common(1)[0][0]] += 1
    return dict(sorted(cnt.items()))
def islands(ob):
    me = ob.data; adj = collections.defaultdict(set)
    for e in me.edges:
        a, b = int(e.vertices[0]), int(e.vertices[1]); adj[a].add(b); adj[b].add(a)
    seen = set(); out = []
    for v0 in range(len(me.vertices)):
        if v0 in seen: continue
        st = [v0]; comp = []; seen.add(v0)
        while st:
            v = st.pop(); comp.append(v)
            for nb in adj[v]:
                if nb not in seen: seen.add(nb); st.append(nb)
        if len(comp) >= 60: out.append(len(comp))
    return sorted(out, reverse=True)
for tag in ('v2b', 'tp', 'ap', 'walk'):
    if tag not in opt: continue
    bpy.ops.wm.open_mainfile(filepath=opt[tag])
    ob = bpy.data.objects['DragonMan_Body']
    R[tag] = {'dom_faces': dom_faces(ob), 'islands': islands(ob),
              'verts': len(ob.data.vertices), 'faces': len(ob.data.polygons)}
    print('[M12]', tag, 'verts', R[tag]['verts'], 'faces', R[tag]['faces'], 'islands', R[tag]['islands'][:12])
json.dump(R, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
if 'v2b' in R and 'tp' in R:
    a, b = R['v2b']['dom_faces'], R['tp']['dom_faces']
    keys = sorted(set(a) | set(b))
    diff = {k: [a.get(k, 0), b.get(k, 0)] for k in keys if a.get(k, 0) != b.get(k, 0)}
    print('[M12] tp vs v2b group-face diffs', diff)
    if 'walk' in R:
        c = R['walk']['dom_faces']
        print('[M12] walk vs tp group-face diffs', {k: [b.get(k, 0), c.get(k, 0)] for k in keys if b.get(k, 0) != c.get(k, 0)})
print('[M12] DONE')
