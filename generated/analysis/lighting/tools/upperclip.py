"""Per-shot upper-half luma mean / % > 235 (and the whole frame). usage: upperclip.py <tag>.."""
import glob,os,sys,numpy as np
from PIL import Image
for t in sys.argv[1:]:
    for f in sorted(glob.glob('build/shots/%s/*.bmp'%t)):
        if os.path.getsize(f)<1000: continue
        a=np.asarray(Image.open(f).convert('RGB'))[::4,::4].astype(float)
        y=0.299*a[...,0]+0.587*a[...,1]+0.114*a[...,2]; u=y[:y.shape[0]//2]
        print(t,os.path.basename(f),'upper %.0f clip %.1f%% | whole %.0f clip %.1f%%'%(u.mean(),(u>235).mean()*100,y.mean(),(y>235).mean()*100))
