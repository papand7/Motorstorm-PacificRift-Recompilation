import sys, numpy as np; sys.path.insert(0,'tools')
from recon import load
jobs=load(sys.argv[1]); ff=np.fromfile(sys.argv[2],dtype='<f4').reshape(-1,2304)
J=np.array([np.frombuffer(j['pcm'],dtype='>f4').astype(np.float32) for j in jobs]); J=J.reshape(-1,2,1152).transpose(0,2,1).reshape(-1,2304) if len(sys.argv)>5 else J
def snr(a,b):
    e=np.sum((a-b)**2); s=np.sum(a**2); return 10*np.log10(s/e) if e>0 else 999
for k in range(int(sys.argv[3]),int(sys.argv[4])):
    best=max(((snr(J[k],ff[m]),m) for m in range(max(0,k-6),min(len(ff),k+6))), key=lambda x:x[0])
    print(k, 'energy %.4f'%np.sqrt(np.mean(J[k]**2)), 'best ff frame', best[1], 'shift', best[1]-k, 'snr %.1f'%best[0], 'maxdiff %.2e'%np.max(np.abs(J[k]-ff[best[1]])))
