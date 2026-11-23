"""Ground brightness sim: invert the current tone curve (exp 0.5, white 1.2, mix 1) on enhanced shots (gi1o, st2), then
apply candidate curves, print ground (bottom 40%) mean/p95/%>235. usage: python groundtone_sim.py"""
import glob,os,numpy as np
from PIL import Image
def s2l(c): return np.where(c<=0.04045,c/12.92,((c+0.055)/1.055)**2.4)
def l2s(c): return np.where(c<=0.0031308,c*12.92,1.055*np.power(np.maximum(c,1e-9),1/2.4)-0.055)
def aces(x): return np.clip((x*(2.51*x+0.03))/(x*(2.43*x+0.59)+0.14),0,1)
def tm(l,e,wp): return aces(l*e)/aces(np.full(1,wp*e))[0]
xs=np.linspace(0,1,4097); cur=tm(xs,0.5,1.2)
def inv(l): return np.interp(l,cur,xs)
def frames(t,sub=4):
    out=[]
    for f in sorted(glob.glob('build/shots/%s/*.bmp'%t)):
        if os.path.getsize(f)<1000: continue
        a=np.asarray(Image.open(f).convert('RGB'))[int(1080*.6)::sub,::sub]/255.0
        out.append(a)
    return out
def stat(a):
    y=0.299*a[...,0]+0.587*a[...,1]+0.114*a[...,2]; y=y*255
    return y.mean(),np.percentile(y,95),(y>235).mean()*100
def cand(l,e,wp,k=1.0,gam=1.0):
    t=np.clip(tm(l,e,wp),0,1); t=t**gam
    return np.clip(l2s(np.clip(l+k*(t-l),0,1)),0,1)
import sys
for t in sys.argv[1:] or ['gi1o','st2']:
    fr=frames(t); lins=[inv(s2l(a)) for a in fr]
    print(t,'current', np.mean([stat(a) for a in fr],0).round(1))
    for e,wp,g in [(0.5,1.2,1),(0.4,1.2,1),(0.35,1.0,1),(0.3,1.0,1),(0.3,1.2,1.0),(0.5,1.2,1.3),(0.5,1.2,1.5),(0.4,1.2,1.3),(0.4,1.0,1.4),(0.5,1.2,1.7)]:
        r=np.mean([stat(cand(l,e,wp,1.0,g)) for l in lins],0).round(1)
        print('  exp %.2f white %.1f gamma %.1f -> mean %.0f p95 %.0f >235 %.1f%%'%((e,wp,g)+tuple(r)))
# original look (no tone curve): plain linear gamma
if 'orig' in sys.argv[0:0] or True:
    for t in ['lt17o']:
        fr=frames(t); print(t,'current',np.mean([stat(a) for a in fr],0).round(1))
        for g in (1.1,1.2,1.3,1.4):
            r=np.mean([stat(l2s(s2l(a)**g)) for a in fr],0).round(1); print('  orig gamma %.1f -> mean %.0f p95 %.0f >235 %.1f%%'%((g,)+tuple(r)))
