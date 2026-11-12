# -*- coding: utf-8 -*-
import json, os
V = r'D:\ai\建模\dragon-men-rebuild\joint-work\verify'
b = json.load(open(os.path.join(V, 'baseline_src.json')))['res']
p = json.load(open(os.path.join(V, 'rays_post.json')))['res']
br = json.load(open(os.path.join(V, 'build_report.json')))
built = [j['key'] for j in br['joints']]
poses = ['bend10', 'bend130', 'bend160', 'bend190', 'twist15', 'twist30', 'twist45', 'bend230', 'bend260', 'bend290']
rows = []
for k in b:
    ps = [x for x in poses if x in b[k]['poses']]
    base = [round(100 * b[k]['poses'][x]['rate6']) for x in ps]
    post = [round(100 * p[k]['poses'][x]['rate6']) for x in ps] if k in p else None
    rows.append(dict(joint=k, built=(k in built), npose=len(ps), pose=ps, base06=base, post06=post,
                     base_worst06=round(100 * b[k]['worst06']),
                     post_worst06=(round(100 * p[k]['worst06']) if k in p else None),
                     base_rad=b[k]['rad'], post_rad=(p[k]['rad'] if k in p else None),
                     base_worst_rad=round(100 * b[k]['worst']),
                     post_worst_rad=(round(100 * p[k]['worst']) if k in p else None)))
json.dump(rows, open(os.path.join(V, 'seam_table.json'), 'w'), indent=1)
print('poses:', poses)
for r in rows:
    print('{:11s} built={:3s} poses={} base06={} post06={} worst06 {}->{}  worstRad({:.3f}) {}->{}'.format(
        r['joint'], str(r['built']), r['npose'], r['base06'], r['post06'], r['base_worst06'],
        r['post_worst06'], r['base_rad'], r['base_worst_rad'], r['post_worst_rad']))
