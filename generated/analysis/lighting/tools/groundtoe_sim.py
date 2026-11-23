"""Sim of the scene-pass luma toe (encoded space, after tone): col *= 1-(1-s)*smoothstep(lo,hi,luma). usage: groundtoe_sim.py <tag>.."""
import glob,os,sys,numpy as np
from PIL import Image
def ss(a,b,x): t=np.clip((x-a)/(b-a),0,1); return t*t*(3-2*t)
def st(a):
    y=(0.299*a[...,0]+0.587*a[...,1]+0.114*a[...,2])*255; return y.mean(),np.percentile(y,95),(y>235).mean()*100
for t in sys.argv[1:]:
    fr=[np.asarray(Image.open(f).convert('RGB'))[::4,::4]/255.0 for f in sorted(glob.glob('build/shots/%s/*.bmp'%t)) if os.path.getsize(f)>1000]
    def sub(a,k): h=a.shape[0]; return a[int(h*.6):] if k=='g' else a[:int(h*.25)]
    print(t,'ground base',np.mean([st(sub(a,'g')) for a in fr],0).round(1),'upper mean',np.mean([st(sub(a,'u'))[0] for a in fr]).round(1))
    for s,lo,hi in ((0.8,0.35,0.6),(0.7,0.35,0.6),(0.7,0.40,0.65),(0.6,0.40,0.65),(0.6,0.35,0.6)):
        o=[];u=[]
        for a in fr:
            y=0.299*a[...,0]+0.587*a[...,1]+0.114*a[...,2]; nosky=((a[...,2]-a[...,0])<0.12); b=a*(1-(1-s)*ss(lo,hi,y)*nosky)[...,None]
            o.append(st(sub(b,'g'))); u.append(st(sub(b,'u'))[0])
        print('  s %.2f ramp %.2f-%.2f -> ground %s upper %.1f'%(s,lo,hi,np.mean(o,0).round(1),np.mean(u)))
