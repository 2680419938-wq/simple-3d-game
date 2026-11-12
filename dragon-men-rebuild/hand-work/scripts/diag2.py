
# -*- coding: utf-8 -*-
"""diag2: per-joint local skin geometry vs bone axis (radii decision support)."""
import bpy, bmesh, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

SRC = r'D:\ai\建模\dragon-men-rebuild\std-rig\DragonMan_Std_TPose.blend'
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['DragonMan_Rig']; body = bpy.data.objects['DragonMan_Body']; me = body.data
MW = np.array(body.matrix_world)
n0v = len(me.vertices)
co = np.empty(n0v*3); me.vertices.foreach_get('co', co); co = co.reshape(-1,3)
PW = co @ MW[:3,:3].T + MW[:3,3]
mats = [m.name for m in me.materials]
skin_i = mats.index('DragonMan_Skin')
vmat = np.zeros(n0v, dtype=np.int32)
for p in me.polygons:
    for vi in p.vertices: vmat[vi] = p.material_index
skin_v = np.where(vmat == skin_i)[0]
polys = [tuple(p.vertices) for p in me.polygons if p.material_index == skin_i]
skin_bvh = BVHTree.FromPolygons([tuple(PW[i]) for i in range(n0v)], polys, all_triangles=False)

grp = {g.index: g.name for g in body.vertex_groups}
domname = np.array([grp.get(max(v.groups, key=lambda g: g.weight).group if len(v.groups) else -1, '') for v in me.vertices], dtype=object)

def perp(u):
    a = Vector((0,0,1))
    if abs(u.dot(a)) > 0.9: a = Vector((0,1,0))
    v = u.cross(a).normalized(); w = u.cross(v).normalized(); return v, w

def raymax(c0, u, n=24, maxd=0.08):
    v, w = perp(u); ds = []
    for i in range(n):
        a = 2*math.pi*i/n
        d = math.cos(a)*v + math.sin(a)*w
        loc, nor, idx, dist = skin_bvh.ray_cast(Vector(c0), d, maxd)
        if loc is not None and dist > 1e-4: ds.append(dist)
    if len(ds) < 6: return None, None, len(ds)
    ds = np.array(ds); med = float(np.median(ds)); keep = ds <= 1.6*med
    return float(ds[keep].max()), med, int(keep.sum())

rows = []
for side in ('Left','Right'):
    for f in ('Thumb','Index','Middle','Ring'):
        for k in (1,2,3):
            b = arm.data.bones['mixamorig:%sHand%s%d'%(side,f,k)]
            par = arm.data.bones['mixamorig:%sHand'%side] if k==1 else arm.data.bones['mixamorig:%sHand%s%d'%(side,f,k-1)]
            J = np.array(list(arm.matrix_world @ b.head_local)); Tl = np.array(list(arm.matrix_world @ b.tail_local))
            u = Tl-J; Lc = float(np.linalg.norm(u)); u = u/Lc
            Lp = 0.55*Lc if k==1 else float(np.linalg.norm(J-np.array(list(arm.matrix_world @ par.head_local))))
            out = []
            for s in (-0.36*Lp, 0.0, 0.5*Lc, 0.34*Lc):
                c0 = J + s*u
                ax = np.abs((PW - c0) @ u); rad = np.linalg.norm((PW - c0) - np.outer((PW-c0) @ u, u), axis=1)
                m = (ax < 0.007) & (rad < 0.07)
                if m.sum():
                    d = rad[m]
                    p50, p90, mx = float(np.percentile(d,50)), float(np.percentile(d,90)), float(d.max())
                else:
                    p50 = p90 = mx = -1
                rmax, rmed, nh = raymax(c0, Vector(u))
                out.append((s, int(m.sum()), p50, p90, mx, rmax, rmed, nh))
            # distance J to nearest skin vert
            dJ = float(np.linalg.norm(PW[skin_v]-J, axis=1).min())
            rows.append((side,f,k,Lc,Lp,round(dJ,4),[(round(o[0],4),o[1],round(o[2],4),round(o[3],4),round(o[4],4),(None if o[5] is None else round(o[5],4)),(None if o[6] is None else round(o[6],4)),o[7]) for o in out]))

print('=== s: vertcnt p50 p90 max | raymax raymed nhits ===')
for side,f,k,Lc,Lp,dJ,out in rows:
    print('%s%-6s%d Lc=%.4f Lp=%.4f dJ=%.4f' % (side[0],f,k,Lc,Lp,dJ))
    for o in out:
        print('   s=%+.4f n=%3d p50=%.4f p90=%.4f max=%.4f ray=%s med=%s nh=%d' % (o[0],o[1],o[2],o[3],o[4],o[5],o[6],o[7]))
