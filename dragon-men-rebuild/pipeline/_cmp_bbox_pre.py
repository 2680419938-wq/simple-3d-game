# -*- coding: utf-8 -*-
"""Sole/height of the already-accepted packages, to know which tolerance is the standing standard."""
import sys, os
sys.path.insert(0, r"D:\ai\建模\dragon-men-rebuild\pipeline")
from glblib import Model
for folder in (r"D:\ai\建模\dragon-men-game", r"D:\ai\建模\dragon-men-game-34", r"D:\ai\建模\dragon-men-game-walk"):
    if not os.path.isdir(folder): continue
    for fn in ("DragonMan_Game.glb", "DragonMan_Game_LOD1.glb", "DragonMan_Game_LOD2.glb", "DragonMan_TPose.glb"):
        p = os.path.join(folder, fn)
        if not os.path.exists(p): continue
        m = Model(p); mn = [1e30] * 3; mx = [-1e30] * 3
        for pr in m.g['meshes'][0]['primitives']:
            a = m.g['accessors'][pr['attributes']['POSITION']]
            for k in range(3):
                mn[k] = min(mn[k], a['min'][k]); mx[k] = max(mx[k], a['max'][k])
        print("%-22s %-24s joints=%2d tris=%6d sole_y=%+.6f height=%.6f"
              % (os.path.basename(folder), fn, len(m.joints), m.tris, mn[1], mx[1] - mn[1]))
