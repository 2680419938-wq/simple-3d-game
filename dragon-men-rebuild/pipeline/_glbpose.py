# -*- coding: utf-8 -*-
"""Pose a shipped GLB directly in glTF space (no Blender) and measure the knee seam.

Rig.solve(dirs, trans) turns world-space bone *direction* targets into local TRS channels
that glblib.Model.skin_verts understands, so a gait can be swept in seconds.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glblib


def rot_align(a, b):
    a = np.asarray(a, float); a /= np.linalg.norm(a)
    b = np.asarray(b, float); b /= np.linalg.norm(b)
    v = np.cross(a, b); c = float(np.dot(a, b)); s = float(np.linalg.norm(v))
    if s < 1e-12:
        if c > 0:
            return np.eye(3)
        p = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
        ax = np.cross(a, p); ax /= np.linalg.norm(ax)
        return 2.0 * np.outer(ax, ax) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1.0 - c) / (s * s))


def mat_quat(R):
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        w = 0.25 * s; x = (R[2, 1] - R[1, 2]) / s; y = (R[0, 2] - R[2, 0]) / s; z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w = (R[2, 1] - R[1, 2]) / s; x = 0.25 * s; y = (R[0, 1] + R[1, 0]) / s; z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w = (R[0, 2] - R[2, 0]) / s; x = (R[0, 1] + R[1, 0]) / s; y = 0.25 * s; z = (R[1, 2] + R[2, 1]) / s
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w = (R[1, 0] - R[0, 1]) / s; x = (R[0, 2] + R[2, 0]) / s; y = (R[1, 2] + R[2, 1]) / s; z = 0.25 * s
    q = np.array([x, y, z, w]); return q / np.linalg.norm(q)


class Rig:
    def __init__(self, path):
        self.path = path
        self.m = glblib.Model(path)
        self.W0 = self.m.world(None, 0.0)
        self.joint_of = {}
        for k, j in enumerate(self.m.joints):
            self.joint_of[self.m.jnames[k]] = j
        self.name_of = {j: self.m.jnames[k] for k, j in enumerate(self.m.joints)}
        self.L0 = {}
        for i in range(self.m.N):
            p = self.m.par.get(i)
            self.L0[i] = np.linalg.inv(self.W0[p]) @ self.W0[i] if p is not None else self.W0[i]
        self.order = sorted(range(self.m.N), key=lambda i: self.m.dep[i])
        self.dom = self.m.dominant_joint_names()

    # ---- rest data ----
    def head0(self, name):
        return self.W0[self.joint_of[name]][:3, 3].copy()

    def dir0(self, name):
        return self.W0[self.joint_of[name]][:3, :3] @ np.array([0.0, 1.0, 0.0])

    # ---- posing ----
    def solve(self, dirs=None, trans=None, heads=None):
        """dirs: {joint: world dir for the bone +Y}; trans: {joint: world head offset}; heads: {joint: absolute world head}."""
        dirs = dirs or {}; trans = trans or {}; heads = heads or {}
        W1 = {}
        posed = {}
        for i in self.order:
            p = self.m.par.get(i)
            name = self.name_of.get(i)
            Wp = W1[p] if p is not None else np.eye(4)
            if name is not None and (name in dirs or name in heads):
                h0 = self.W0[i][:3, 3]; R0 = self.W0[i][:3, :3]
                d = np.asarray(dirs.get(name, R0 @ np.array([0.0, 1.0, 0.0])), float)
                R1 = rot_align(R0 @ np.array([0.0, 1.0, 0.0]), d) @ R0
                if p is not None:
                    hp0 = self.W0[p][:3, 3]
                    h1 = Wp[:3, 3] + Wp[:3, :3] @ (h0 - hp0)
                else:
                    h1 = h0.copy()
                if name in heads:
                    h1 = np.asarray(heads[name], float)
                else:
                    h1 = h1 + np.asarray(trans.get(name, (0.0, 0.0, 0.0)), float)
                M = np.eye(4); M[:3, :3] = R1; M[:3, 3] = h1
                W1[i] = M; posed[i] = True
            else:
                W1[i] = Wp @ self.L0[i]
        ch = {}
        for i in posed:
            p = self.m.par.get(i)
            Wp = W1[p] if p is not None else np.eye(4)
            M = np.linalg.inv(Wp) @ W1[i]
            R = M[:3, :3]
            s = np.array([np.linalg.norm(R[:, 0]), np.linalg.norm(R[:, 1]), np.linalg.norm(R[:, 2])])
            Rn = R / s
            ch[i] = {
                'translation': (np.array([0.0]), M[:3, 3].reshape(1, 3), 'LINEAR'),
                'rotation': (np.array([0.0]), mat_quat(Rn).reshape(1, 4), 'LINEAR'),
                'scale': (np.array([0.0]), s.reshape(1, 3), 'LINEAR'),
            }
        return ch, W1

    def verts(self, ch):
        return self.m.skin_verts(ch, 0.0) if ch else self.m.skin_verts(None, 0.0)

    # ---- measurement ----
    def sets(self, side):
        side = side.upper()
        A = np.where(self.dom == 'thigh.' + side)[0]
        B = np.where(np.isin(self.dom, ['shin.' + side, 'foot.' + side,
                                       'toe.01.' + side, 'toe.02.' + side, 'toe.03.' + side]))[0]
        return A, B


def min_pair_dist(A, B, chunk=400):
    best = 1e9; pair = None
    for i in range(0, A.shape[0], chunk):
        a = A[i:i + chunk]
        d = np.linalg.norm(a[:, None, :] - B[None, :, :], axis=2)
        k = np.unravel_index(np.argmin(d), d.shape)
        if d[k] < best:
            best = float(d[k]); pair = (i + k[0], k[1])
    return best, pair


def knee_deg(rig, W, side):
    """Angle between thigh and shin bone directions in the posed world."""
    t = W[rig.joint_of['thigh.' + side]][:3, :3] @ np.array([0, 1.0, 0])
    s = W[rig.joint_of['shin.' + side]][:3, :3] @ np.array([0, 1.0, 0])
    c = float(np.dot(t / np.linalg.norm(t), s / np.linalg.norm(s)))
    return np.degrees(np.arccos(np.clip(c, -1, 1)))