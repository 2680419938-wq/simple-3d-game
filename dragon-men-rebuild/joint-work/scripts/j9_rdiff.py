# -*- coding: utf-8 -*-
import os, json
from PIL import Image
import numpy as np
R = r'D:\ai\建模\dragon-men-rebuild\joint-work\renders'
keys = ['L_shoulder','R_shoulder','L_elbow','R_elbow','L_wrist','R_wrist','L_hip','R_hip','neck','waist','waist1']
out = []
for k in keys:
    for suf in ('side','front'):
        a = np.asarray(Image.open(os.path.join(R,'seamBEFORE_%s_bend90_%s.png'%(k,suf))).convert('RGB'), np.float32)
        b = np.asarray(Image.open(os.path.join(R,'seamAFTER_%s_bend90_%s.png'%(k,suf))).convert('RGB'), np.float32)
        d = np.abs(a-b)
        rmse = float(np.sqrt(((a-b)**2).mean()))
        frac = float((d.max(axis=2) > 8).mean())
        out.append(dict(joint=k, view=suf, rmse=round(rmse,3), changed_frac=round(frac,4),
                        before=os.path.join(R,'seamBEFORE_%s_bend90_%s.png'%(k,suf)),
                        after=os.path.join(R,'seamAFTER_%s_bend90_%s.png'%(k,suf))))
        print('{:11s} {:5s} rmse={:7.2f}  pixels changed>8: {:6.2f}%'.format(k, suf, rmse, 100*frac))
json.dump(out, open(r'D:\ai\建模\dragon-men-rebuild\joint-work\verify\render_diff.json','w'), indent=1)
