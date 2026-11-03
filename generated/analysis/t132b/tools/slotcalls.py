# find indirect calls of vtable slot SLOT whose object was loaded from field OFF: python slotcalls.py SLOT OFF
import sys,os
sys.path.insert(0,os.path.dirname(__file__))
from common import *
from graph import f2
from up import nm
SLOT=int(sys.argv[1],16); OFF=int(sys.argv[2],16)
for a in range(0x10200,0xCBDD68,4):
    x=w(a)
    if x>>26==32 and (x&0xffff)==SLOT:   # lwz rF, SLOT(rVT)
        rvt=(x>>16)&31
        # rVT loaded by lwz rVT,0(rObj); rObj loaded by lwz rObj,OFF(rBase) within 12 insns back
        for b in range(a-4,a-48,-4):
            y=w(b)
            if y>>26==32 and ((y>>21)&31)==rvt and (y&0xffff)==0:
                robj=(y>>16)&31
                for c in range(b-4,b-48,-4):
                    z=w(c)
                    if z>>26==32 and ((z>>21)&31)==robj:
                        if (z&0xffff)==OFF: print('%#x slot %#x obj from %#x(r%d) in %s'%(a,SLOT,OFF,(z>>16)&31,nm(f2(a))[:100]))
                        break
                break
