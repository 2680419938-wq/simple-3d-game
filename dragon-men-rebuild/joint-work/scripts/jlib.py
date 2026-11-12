# -*- coding: utf-8 -*-
"""Shared helpers for body-joint transition cuffs (shoulder/elbow/wrist/hip/neck/waist)."""
import bpy, math
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree

SKIN = 'DragonMan_Skin'
MESHES = ('DragonMan_Body', 'DragonMan_Foot.L', 'DragonMan_Foot.R')

# (joint_key, child_bone, parent_bone, twist_dominant)
JOINTS = [
    ('L_shoulder', 'mixamorig:LeftArm',      'mixamorig:LeftShoulder', True),
    ('R_shoulder', 'mixamorig:RightArm',     'mixamorig:RightShoulder', True),
    ('L_elbow',    'mixamorig:LeftForeArm',  'mixamorig:LeftArm',      False),
    ('R_elbow',    'mixamorig:RightForeArm', 'mixamorig:RightArm',     False),
    ('L_wrist',    'mixamorig:LeftHand',     'mixamorig:LeftForeArm',  False),
    ('R_wrist',    'mixamorig:RightHand',    'mixamorig:RightForeArm', False),
    ('L_hip',      'mixamorig:LeftUpLeg',    'mixamorig:Hips',         False),
    ('R_hip',      'mixamorig:RightUpLeg',   'mixamorig:Hips',         False),
    ('neck',       'mixamorig:Neck',         'mixamorig:Spine2',       True),
    ('neck1',      'mixamorig:Neck1',        'mixamorig:Neck',         True),
    ('waist',      'mixamorig:Spine',        'mixamorig:Hips',         True),
    ('waist1',     'mixamorig:Spine1',       'mixamorig:Spine',        True),
    ('chest',      'mixamorig:Spine2',       'mixamorig:Spine1',       True),
]
Z = np.array([0.0, 0.0, 1.0])
Y = np.array([0.0, 1.0, 0.0])


def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def bh(arm, nm):
    b = arm.data.bones[nm]
    return np.array(list(arm.matrix_world @ b.head_local)), np.array(list(arm.matrix_world @ b.tail_local))


def flex_axis(u):
    c = np.cross(u, Z)
    if np.linalg.norm(c) < 0.2:
        c = np.cross(u, Y)
    return unit(c)


def clear_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def set_rot(arm, nm, wax, deg):
    """Rotate one bone by deg about world axis wax (all other bones zeroed)."""
    clear_pose(arm)
    if deg:
        pb = arm.pose.bones[nm]
        q = pb.bone.matrix_local.to_3x3().inverted() @ Vector(wax)
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = Quaternion(q.normalized(), math.radians(deg))
        bpy.context.view_layer.update()


def obj_bvh(objs, dg, mat_filter=None):
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
        mats = [m.name if m else '' for m in me.materials]
        verts.extend(map(tuple, co))
        for p in me.polygons:
            if mat_filter is not None and mats[p.material_index] not in mat_filter:
                continue
            polys.append(tuple(v + off for v in p.vertices))
        off += len(co)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=False)


FIB = []
GA = math.pi * (3 - math.sqrt(5))
for _i in range(26):
    _z = 1 - 2 * (_i + 0.5) / 26
    _r = math.sqrt(max(0.0, 1 - _z * _z))
    _th = GA * _i
    FIB.append(Vector((_r * math.cos(_th), _r * math.sin(_th), _z)))


def local_radius(bvh, J, rmax=0.6):
    ds = []
    for d in FIB:
        loc, nor, idx, dist = bvh.ray_cast(Vector(J), d, rmax)
        if loc is not None and dist > 1e-4:
            ds.append(dist)
    if not ds:
        return 0.02, 0
    return float(np.median(ds)), len(ds)


def ring_dirs(ax, n):
    ea = Z if abs(ax[2]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(ax, ea)
    u = unit(u)
    v = np.cross(ax, u)
    return [(math.cos(2 * math.pi * i / n) * u + math.sin(2 * math.pi * i / n) * v, i) for i in range(n)]


def measure(bvh, J, dirs, rad):
    hit = 0
    miss = []
    for d, i in dirs:
        loc, nor, idx, dist = bvh.ray_cast(Vector(J + d * rad), Vector(-d), rad)
        if loc is not None:
            hit += 1
        else:
            miss.append(i)
    return hit, miss


def mat_tally(objs, dg, J, rad):
    out = {}
    for ob in objs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        MW = np.array(ev.matrix_world)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
        near = np.linalg.norm(co - J, axis=1) < rad
        mats = [m.name if m else '' for m in me.materials]
        for p in me.polygons:
            if near[p.vertices[0]]:
                k = mats[p.material_index]
                out[k] = out.get(k, 0) + 1
        ev.to_mesh_clear()
    return out
