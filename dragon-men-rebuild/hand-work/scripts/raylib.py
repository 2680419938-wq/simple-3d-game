
# -*- coding: utf-8 -*-
"""Ring ray-occlusion measurement for finger joints. Shared by baseline + post-build checks."""
import bpy, math
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree

FING = ('Thumb', 'Index', 'Middle', 'Ring')
SIDES = (('Left', 'L'), ('Right', 'R'))


def joint_list(arm):
    """(side, finger, k, bone_name, parent_bone_name)"""
    out = []
    for side, tag in SIDES:
        for f in FING:
            for k in (1, 2, 3):
                nm = 'mixamorig:%sHand%s%d' % (side, f, k)
                par = 'mixamorig:%sHand' % side if k == 1 else 'mixamorig:%sHand%s%d' % (side, f, k - 1)
                out.append((side, tag, f, k, nm, par))
    return out


def flex_axis(arm, side, f, k):
    """Anatomic flexion axis in the bone's local space (same convention as probe_render2.py)."""
    b1 = arm.data.bones['mixamorig:%sHand%s1' % (side, f)]
    b3 = arm.data.bones['mixamorig:%sHand%s3' % (side, f)]
    hb = arm.data.bones['mixamorig:%sHand' % side]
    fdir = (b3.tail_local - b1.head_local).normalized()
    pn = (hb.tail_local - hb.head_local).normalized()
    ax = fdir.cross(pn).normalized()
    pb = arm.pose.bones['mixamorig:%sHand%s%d' % (side, f, k)]
    return (pb.bone.matrix_local.to_3x3().inverted() @ ax).normalized(), ax


def clear_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def set_bend(arm, side, f, k, deg):
    clear_pose(arm)
    if deg:
        lax, _ = flex_axis(arm, side, f, k)
        pb = arm.pose.bones['mixamorig:%sHand%s%d' % (side, f, k)]
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = Quaternion(lax, math.radians(deg))
    bpy.context.view_layer.update()


def world_bvh(objs, dg):
    verts = []
    polys = []
    off = 0
    for ob in objs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        MW = np.array(ev.matrix_world)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
        verts.extend(map(tuple, co))
        for p in me.polygons:
            polys.append(tuple(v + off for v in p.vertices))
        off += len(co)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=False)


def ring_dirs(axis_u, axis_v, n):
    return [(math.cos(2 * math.pi * i / n) * axis_u + math.sin(2 * math.pi * i / n) * axis_v, i) for i in range(n)]


def measure_joint(bvh, J, dirs, RAD, skin_bvh=None):
    """Cast from J+d*RAD toward J. Returns (hits, missing indices, min hit distance per dir)."""
    hits = 0
    miss = []
    dists = []
    for d, i in dirs:
        loc, nor, idx, dist = bvh.ray_cast(Vector(J + d * RAD), Vector(-d), RAD)
        if loc is not None:
            hits += 1
            dists.append(dist)
        else:
            miss.append(i)
            dists.append(None)
    return hits, miss, dists
