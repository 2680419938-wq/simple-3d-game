# -*- coding: utf-8 -*-
"""Crop the knee region from the same-camera before/after side renders and lay them out side by side."""
from PIL import Image
NEW = r'D:\ai\建模\dragon-men-game-walk\renders\idle_f01_side.png'
OLD = r'D:\ai\建模\dragon-men-game-walk\renders\_before_game32\idle_f01_side.png'
OUT = r'D:\ai\建模\dragon-men-game-walk\renders\_knee_compare.png'
BOX = (40, 380, 340, 700)
a = Image.open(OLD).convert('RGB').crop(BOX).resize((900, 960), Image.LANCZOS)
b = Image.open(NEW).convert('RGB').crop(BOX).resize((900, 960), Image.LANCZOS)
c = Image.new('RGB', (1810, 960), (30, 30, 30))
c.paste(a, (0, 0)); c.paste(b, (910, 0))
c.save(OUT)
print('[C] before(left) vs after(right) ->', OUT, a.size)
