import os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _glbpose import Rig
from _walksearch import Walk, score, NF, GLB

rig = Rig(GLB)
p = dict(DUTY=0.62, A=0.055, MID=0.6045, AMP=0.0045, ROLL=2.6, SWAY=0.006, YAW=2.0,
         LIFT=0.016, ARM=11.0, ELBOW=9.0, TAIL=2.6)
w = Walk(rig, **p)
res = w.evaluate()
for i in range(NF):
    t = i/float(NF-1)
    phL = t % 1.0; phR = (t+0.5) % 1.0
    print('f%02d pel %.4f kneeL %5.2f kneeR %5.2f liftL %.4f liftR %.4f phL %.2f phR %.2f over L %+.4f R %+.4f'
          % (i+1, res['pel'][i], res['knee']['L'][i], res['knee']['R'][i],
             res['lift']['L'][i], res['lift']['R'][i], phL, phR,
             res['anklegap']['L'][i], res['anklegap']['R'][i]))
