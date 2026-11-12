# -*- coding: utf-8 -*-
import sys, numpy as np
sys.path.insert(0, r"D:\ai\建模\dragon-men-rebuild\pipeline")
from glblib import Model
a = Model(r"D:\ai\建模\dragon-men-game-34\DragonMan_Game.glb")
b = Model(r"D:\ai\建模\dragon-men-game\DragonMan_Game.glb")
print("game34 joints", len(a.joints), " game32 joints", len(b.joints))
na = {a.nodes[j].get("name"): j for j in a.joints}
nb = {b.nodes[j].get("name"): j for j in b.joints}
common = [n for n in na if n in nb]
print("common bones", len(common), "extra in 34", sorted(set(na) - set(nb)))
for an in ("Idle_Lively", "Walk"):
    if an not in a.anims or an not in b.anims:
        print(an, "present?", an in a.anims, an in b.anims); continue
    ca, cb = a.anims[an], b.anims[an]
    worst = {}
    for n in common:
        for path in ("translation", "rotation", "scale"):
            if path in ca[na[n]] and path in cb[nb[n]]:
                va = ca[na[n]][path][1]; vb = cb[nb[n]][path][1]
                if va.shape != vb.shape:
                    worst[path] = 99.0
                else:
                    worst[path] = max(worst.get(path, 0.0), float(np.abs(va - vb).max()))
    print(an, {k: "%.3e" % v for k, v in worst.items()},
          "keys", len(ca[na["head"]]["rotation"][0]), len(cb[nb["head"]]["rotation"][0]))
