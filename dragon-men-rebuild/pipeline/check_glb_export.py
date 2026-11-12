
"""GLB 动画导出检查器（不依赖 Blender）。
用法: python check_glb_export.py <34版GLB目录> <32版对照GLB>
检查项：
 1. 每根骨的 rest TRS 与每条动画首帧是否一致（这是 0.6667 缩放的病根所在）
 2. 四条文件骨架 TRS 一致性
 3. 甲片顶点在 Idle/Walk 相对 bind 的位移
 4. Walk 逐帧最低点（glTF Y-up）
"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glblib import Model, acc

def scan_rest_vs_anim(m):
    bad=[]
    for anim,ch in m.anims.items():
        for j,paths in ch.items():
            n=m.nodes[j]
            rt=np.array(n.get('translation',[0,0,0]),float)
            rr=np.array(n.get('rotation',[0,0,0,1]),float)
            rs=np.array(n.get('scale',[1,1,1]),float)
            dt=np.abs(paths['translation'][1][0]-rt).max() if 'translation' in paths else 0
            dr=min(np.abs(paths['rotation'][1][0]-rr).max(), np.abs(paths['rotation'][1][0]+rr).max()) if 'rotation' in paths else 0
            ds=np.abs(paths['scale'][1][0]-rs).max() if 'scale' in paths else 0
            if ds>1e-4:
                bad.append((anim, n.get('name'), 'scale', round(float(ds),4), list(np.round(rs,4)), list(np.round(paths['scale'][1][0],4))))
    return bad

def main(d34):
    files=[('LOD0','DragonMan_Game.glb'),('LOD1','DragonMan_Game_LOD1.glb'),('LOD2','DragonMan_Game_LOD2.glb'),('TPOSE','DragonMan_TPose.glb')]
    ref=None
    for tag,fn in files:
        p=os.path.join(d34,fn)
        if not os.path.exists(p): continue
        m=Model(p); W=m.world(None,0.0)
        sig=[(m.jnames[i], tuple(np.round(W[m.joints[i]][:3,3],5))) for i in range(len(m.joints))]
        if ref is None: ref=sig
        print("%-6s joints=%2d tris=%6d anims=%s skeleton_same=%s" % (tag,len(m.joints),m.tris,[a for a in m.anims],sig==ref))
        bad=scan_rest_vs_anim(m)
        if bad:
            print("   !! rest 与动画首帧不一致（缩放）:")
            for b in bad: print("     ", b)
        else:
            print("   rest vs anim: OK")
    m=Model(os.path.join(d34,'DragonMan_Game.glb'))
    dom=[]
    for pr in m.g['meshes'][0]['primitives']:
        J=acc(m.g,m.bin,pr['attributes']['JOINTS_0']).astype(int)
        Wt=acc(m.g,m.bin,pr['attributes']['WEIGHTS_0']); k=np.argmax(Wt,axis=1)
        dom.append(np.array([m.jnames[J[i,k[i]]] for i in range(J.shape[0])]))
    dom=np.concatenate(dom); armor=np.char.startswith(dom.astype(str),'armor_knee')
    Vrest=m.skin_verts(None,0.0)
    for anim in m.anims:
        ch=m.anims[anim]
        tmax=max(float(v['rotation'][0][-1]) for v in ch.values() if 'rotation' in v)
        worstA=0; worstY=1e9; below=0
        for f in range(33):
            t=tmax*f/32.0 if anim=='Walk' else tmax*f/120.0
            V=m.skin_verts(ch,t)
            if armor.any():
                worstA=max(worstA, float(np.linalg.norm(V[armor]-Vrest[armor],axis=1).max()))
            worstY=min(worstY, float(V[:,1].min()))
            if V[:,1].min()<0: below+=1
        if not armor.any():
            print("%s: 无甲片顶点 | 最低点 %.5f | 低于地面帧数 %d" % (anim, worstY, below))
        else:
            print("%s: 甲片相对 bind 最大位移 %.4f m | 最低点 %.5f | 低于地面帧数 %d" % (anim, worstA, worstY, below))

if __name__=='__main__':
    main(sys.argv[1] if len(sys.argv)>1 else r'D:\ai\建模\dragon-men-game-34')
