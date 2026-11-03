# find stw to displacement D (signed hex) anywhere: python fieldw.py -0x24b4 ...
import sys,os
sys.path.insert(0,os.path.dirname(__file__))
from common import *
from graph import f2
from up import nm
for ds in sys.argv[1:]:
    D=int(ds,16)&0xffff
    print('== disp',ds)
    for a in range(0x10200,0xCBDD68,4):
        x=w(a)
        if x>>26 in (36,) and (x&0xffff)==D:
            print('  %#x stw r%d,(r%d) in %s'%(a,(x>>21)&31,(x>>16)&31,nm(f2(a))[:100]))
