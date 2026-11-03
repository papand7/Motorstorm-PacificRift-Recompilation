"""T169: D1 against F1 dumps by index: per-frame difference, mean luminance, high-frequency energy, and a side-by-side PNG."""
import glob
import numpy as np
from PIL import Image
A='../ab/'; D=sorted(glob.glob(A+'runtime-D1-*/frames/*.bmp')); F=sorted(glob.glob(A+'runtime-F1-*/frames/*.bmp'))
rows=[]
for i,(a,b) in enumerate(zip(D,F)):
    x=np.asarray(Image.open(a).convert('RGB'),float); y=np.asarray(Image.open(b).convert('RGB'),float)
    hf=lambda z:np.abs(np.diff(z.mean(2),axis=1)).mean()
    print(i,'meanD %.1f meanF %.1f absdiff %.2f pct>16 %.2f hfD %.2f hfF %.2f'%(x.mean(),y.mean(),np.abs(x-y).mean(),100*(np.abs(x-y).max(2)>16).mean(),hf(x),hf(y)))
    rows.append((a,b))
c=Image.new('RGB',(1280,360*len(rows)))
for i,(a,b) in enumerate(rows):
    c.paste(Image.open(a).convert('RGB').resize((640,360)),(0,360*i)); c.paste(Image.open(b).convert('RGB').resize((640,360)),(640,360*i))
c.save('../img/D1_F1_dumps.png')
