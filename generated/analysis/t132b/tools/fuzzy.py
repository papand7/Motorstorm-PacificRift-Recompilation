# fuzzy retail->dev: search dev text for the retail function's first N masked words. python fuzzy.py N addr...
import sys,os,array,bisect
sys.path.insert(0,os.path.dirname(__file__))
from common import *
import devdis as D
def mask(x):
    op=x>>26
    if op in (18,16): return x&0xFC000003
    if ((x>>16)&31)==2 and op in (14,15,32,34,36,40,48,50,58,62,38,52,54): return x&0xFFFF0000
    return x
from names import demangle
from graph import S
N=int(sys.argv[1])
# dev text words
va0,o0,fs0=D.segs[0]; lo=va0; hi=va0+fs0-(fs0%4)
o=o0; dw=array.array('I',D.d[o:o+(hi-lo)]); dw.byteswap()
dm=[mask(x) for x in dw]
idx={}
for i in range(len(dm)-N):
    idx.setdefault(tuple(dm[i:i+N]),[]).append(i)
for x in sys.argv[2:]:
    a=int(x,16); sig=tuple(mask(w(a+4*k)) for k in range(N))
    hits=idx.get(sig,[])
    ns=[D.name(lo+4*i) for i in hits[:3]]
    print('%#x'%a, len(hits), ' || '.join(demangle([n.split('+')[0] for n in ns])) if ns else '', [n for n in ns if '+' in n][:1])
