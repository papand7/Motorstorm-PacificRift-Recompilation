# indirect call sites of slot SLOT with float arg f1 prepared nearby
import sys,os
sys.path.insert(0,os.path.dirname(__file__))
from common import *
from graph import f2
from up import nm
SLOT=int(sys.argv[1],16)
for a in range(0x10200,0xCBDD68,4):
    x=w(a)
    if x in (0x4e800421,0x4e800021):
        ok=False; f1=False
        for b in range(a-4,a-60,-4):
            y=w(b)
            if y>>26==32 and (y&0xffff)==SLOT and ((y>>16)&31)!=1 and ((y>>16)&31)!=2: ok=True
            if (y>>26==63 and ((y>>21)&31)==1 and (y&0x7fe)==0x90) or (y>>26 in (48,50) and ((y>>21)&31)==1): f1=True
            if y in (0x4e800421,0x4e800021) or (y>>26==18 and y&1): break
        if ok and f1: print('%#x in %s'%(a,nm(f2(a))[:110]))
