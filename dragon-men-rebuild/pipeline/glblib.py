
import json, struct, os, sys
import numpy as np

def load(p):
    b=open(p,'rb').read(); off=12; length=struct.unpack('<III',b[:12])[2]; js=None; bin_=None
    while off<length:
        clen,ctype=struct.unpack('<II',b[off:off+8]); off+=8
        chunk=b[off:off+clen]; off+=clen
        if ctype==0x4E4F534A: js=json.loads(chunk)
        elif ctype==0x004E4942: bin_=chunk
    return js,bin_

CT={5126:('f',4),5123:('H',2),5121:('B',1),5125:('I',4),5122:('h',2),5120:('b',1)}
NC={'VEC3':3,'VEC4':4,'SCALAR':1,'MAT4':16,'VEC2':2}
def acc(g,b,i):
    a=g['accessors'][i]; bv=g['bufferViews'][a['bufferView']]
    fmt,size=CT[a['componentType']]; n=NC[a['type']]
    off=bv.get('byteOffset',0)+a.get('byteOffset',0); stride=bv.get('byteStride', size*n)
    out=np.zeros((a['count'],n))
    for k in range(a['count']):
        out[k]=struct.unpack_from('<'+fmt*n, b, off+k*stride)
    return out

def trs(t,r,s):
    x,y,z,w=r
    R=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    M=np.eye(4); M[:3,:3]=R*np.array(s); M[:3,3]=t; return M

def slerp(a,b,u):
    d=float(np.dot(a,b))
    if d<0: b=-b; d=-d
    if d>0.9995:
        q=a+u*(b-a); return q/np.linalg.norm(q)
    th=np.arccos(np.clip(d,-1,1))
    return (np.sin((1-u)*th)*a+np.sin(u*th)*b)/np.sin(th)

def sample(times, vals, t, interp):
    if t<=times[0]: return vals[0]
    if t>=times[-1]: return vals[-1]
    i=int(np.searchsorted(times,t))-1; i=max(0,min(i,len(times)-2))
    u=(t-times[i])/(times[i+1]-times[i])
    if interp=='STEP': return vals[i]
    if vals.shape[1]==4: return slerp(vals[i],vals[i+1],u)
    return vals[i]+u*(vals[i+1]-vals[i])

class Model:
    def __init__(self, path):
        self.g,self.bin=load(path)
        g=self.g
        self.nodes=g['nodes']; self.N=len(self.nodes)
        self.par={}
        for i,n in enumerate(self.nodes):
            for c in n.get('children',[]): self.par[c]=i
        self.dep=self._depths()
        self.anims={}
        for a in g.get('animations',[]):
            ch={}
            for c in a['channels']:
                s=a['samplers'][c['sampler']]
                ch.setdefault(c['target']['node'],{})[c['target']['path']]=(
                    acc(g,self.bin,s['input'])[:,0], acc(g,self.bin,s['output']),
                    s.get('interpolation','LINEAR'))
            self.anims[a.get('name','?')]=ch
        self.skin=g['skins'][0]
        self.joints=self.skin['joints']
        self.jnames=[self.nodes[j].get('name') for j in self.joints]
        self.ibm=acc(g,self.bin,self.skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1)
        self.meshnode=None
        for i,n in enumerate(self.nodes):
            if 'mesh' in n: self.meshnode=i; break
        self.tris=sum(g['accessors'][p['indices']]['count']//3 for m in g['meshes'] for p in m['primitives'])
    def _depths(self):
        d={}
        for i in range(self.N):
            k=0; j=i
            while j in self.par: j=self.par[j]; k+=1
            d[i]=k
        return d
    def world(self, ch, t):
        W={}
        order=sorted(range(self.N), key=lambda i:self.dep[i])
        for i in order:
            n=self.nodes[i]
            tr=np.array(n.get('translation',[0,0,0]),float)
            ro=np.array(n.get('rotation',[0,0,0,1]),float)
            sc=np.array(n.get('scale',[1,1,1]),float)
            if ch and i in ch:
                c=ch[i]
                if 'translation' in c: tr=sample(c['translation'][0],c['translation'][1],t,c['translation'][2])
                if 'rotation' in c:    ro=sample(c['rotation'][0],c['rotation'][1],t,c['rotation'][2])
                if 'scale' in c:       sc=sample(c['scale'][0],c['scale'][1],t,c['scale'][2])
            M=trs(tr,ro,sc)
            W[i]=W[self.par[i]]@M if i in self.par else M
        return W
    def skin_verts(self, ch, t):
        g=self.g
        W=self.world(ch,t)
        mesh=g['meshes'][self.nodes[self.meshnode]['mesh']]
        MW=W[self.meshnode]
        pal=np.stack([W[j]@self.ibm[k] for k,j in enumerate(self.joints)])
        out=[]
        for pr in mesh['primitives']:
            P=acc(g,self.bin,pr['attributes']['POSITION'])
            if 'JOINTS_0' not in pr['attributes']:
                out.append(MW[:3,:3]@P.T+MW[:3,3:4]); continue
            J=acc(g,self.bin,pr['attributes']['JOINTS_0']).astype(int)
            Wt=acc(g,self.bin,pr['attributes']['WEIGHTS_0'])
            acc4=np.zeros((P.shape[0],4))
            for k in range(4):
                M=pal[J[:,k]]                     # (n,4,4)
                v=np.einsum('nij,nj->ni', M[:,:3,:3], P)+M[:,:3,3]
                acc4[:,:3]+=v*Wt[:,k:k+1]
            out.append(acc4[:,:3].T)
        V=np.hstack(out).T
        return (MW[:3,:3]@V.T+MW[:3,3:4]).T
    def dominant_joint_names(self):
        g=self.g
        mesh=g['meshes'][self.nodes[self.meshnode]['mesh']]
        names=[]
        for pr in mesh['primitives']:
            J=acc(g,self.bin,pr['attributes']['JOINTS_0']).astype(int)
            Wt=acc(g,self.bin,pr['attributes']['WEIGHTS_0'])
            k=np.argmax(Wt,axis=1)
            for i in range(J.shape[0]):
                names.append(self.jnames[J[i,k[i]]])
        return np.array(names)
