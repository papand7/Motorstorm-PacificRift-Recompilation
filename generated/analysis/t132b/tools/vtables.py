# find vtable-like runs of OPD pointers in .data/.rodata; write vtables.json {start: [fn entry addrs]}
import json,os,sys
sys.path.insert(0,os.path.dirname(__file__))
from common import *
OPD0,OPD1=0x107b8c8,0x1097bf0
def isopd(v): return OPD0<=v<OPD1 and (v-OPD0)%8==0
res={}
for lo,hi in ((0xd9ddc8,0xf6a500+0xbe580),(0x10311a0,0x107b2bc)):
    a=lo&~3
    while a<hi:
        if isopd(w(a)):
            b=a
            while b<hi and (isopd(w(b)) ):
                b+=4
            if b-a>=12: res['%#x'%a]=[w(x) for x in range(a,b,4)]
            a=b
        else: a+=4
# resolve OPD -> code addr
out={k:['%#x'%w(o) for o in v] for k,v in res.items()}
json.dump(out,open(os.path.join(os.path.dirname(__file__),'..','vtables.json'),'w'))
print(len(out)); big=sorted(out.items(),key=lambda kv:-len(kv[1]))[:15]
for k,v in big: print(k,len(v))
