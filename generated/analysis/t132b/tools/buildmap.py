# map retail functions -> developer-build symbol names by masked signature (full-length and 20-word prefix)
import sys,os,json,pickle,bisect,array
sys.path.insert(0,os.path.dirname(__file__))
from common import *
import devdis as D
from match import mask
import struct
def devwords(a,end):
    return tuple(mask(D.w(x)) for x in range(a,end,4))
full={};pre={}
code=D.code
for i,a in enumerate(code):
    n=D.byaddr[a]
    end=code[i+1] if i+1<len(code) else a+0x400
    if end-a>0x8000 or end-a<16: continue
    try: s=devwords(a,end)
    except Exception: continue
    full.setdefault(s,[]).append(n)
    if len(s)>=20: pre.setdefault(s[:20],[]).append(n)
out={}
for f in fs:
    a=int(f['start'],16); b=int(f['end'],16)
    s=tuple(mask(w(x)) for x in range(a,b,4))
    if s in full: out['%#x'%a]=('full',full[s][:3])
    elif len(s)>=20 and s[:20] in pre: out['%#x'%a]=('prefix',pre[s[:20]][:3])
json.dump(out,open(os.path.join(os.path.dirname(__file__),'..','retail_devnames.json'),'w'),indent=0)
print(len(out),'matched of',len(fs))
