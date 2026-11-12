import os
from PIL import Image
import numpy as np
R=r'D:\ai\建模\dragon-men-rebuild\joint-work\renders'
for k in ['waist','L_wrist','R_hip','L_hip']:
    for suf in ['side','front']:
        pa=os.path.join(R,'seamBEFORE_%s_bend0_%s.png'%(k,suf)); pb=os.path.join(R,'seamAFTER_%s_bend0_%s.png'%(k,suf))
        if not (os.path.exists(pa) and os.path.exists(pb)): print('MISSING',k,suf); continue
        A=np.asarray(Image.open(pa).convert('RGB'),np.float32); B=np.asarray(Image.open(pb).convert('RGB'),np.float32)
        d=np.abs(A-B); print('%-8s %-5s rmse=%6.2f changed>8: %5.2f%%'%(k,suf,np.sqrt(((A-B)**2).mean()),100*(d.max(axis=2)>8).mean()))
