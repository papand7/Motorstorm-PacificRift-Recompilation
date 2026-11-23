import sys,glob,os
import numpy as np
from PIL import Image
def st(a):
    l=0.299*a[...,0]+0.587*a[...,1]+0.114*a[...,2]
    return l.mean(),np.percentile(l,95),(l>235).mean()*100
def run(path):
    im=np.asarray(Image.open(path).convert('RGB')).astype(float)
    h=im.shape[0]
    g=st(im[int(h*.6):]);w=st(im)
    return g,w
if __name__=="__main__":
    for p in sys.argv[1:]:
        fs=[p] if os.path.isfile(p) else sorted(f for f in glob.glob(p+'/*.bmp') if os.path.getsize(f)>1000)
        rs=[run(f) for f in fs]
        if not rs: continue
        m=np.mean([[*r[0],*r[1]] for r in rs],axis=0)
        print("%-40s n=%2d ground mean %.0f p95 %.0f >235 %.1f%% | whole mean %.0f p95 %.0f >235 %.1f%%"%((p[-40:],len(rs))+tuple(m)))
