"""Sim of a sunlit-ground luminance scale on real shots (weight ~ lit-ish pixels). usage: groundscale_sim.py <tag>"""
import glob,os,sys,numpy as np
from PIL import Image
t=sys.argv[1]
fr=[np.asarray(Image.open(f).convert('RGB'))[int(1080*.6)::4,::4]/255.0 for f in sorted(glob.glob('build/shots/%s/*.bmp'%t)) if os.path.getsize(f)>1000]
def st(a):
    y=(0.299*a[...,0]+0.587*a[...,1]+0.114*a[...,2])*255; return y.mean(),np.percentile(y,95),(y>235).mean()*100
print(t,'base',np.mean([st(a) for a in fr],0).round(1))
for s in (0.85,0.75,0.7,0.65):
    o=[]
    for a in fr:
        y=0.299*a[...,0]+0.587*a[...,1]+0.114*a[...,2]; w=np.clip((y-0.25)/0.2,0,1)[...,None]
        o.append(st(a*(1-w*(1-s))))
    print(s,np.mean(o,0).round(1))
