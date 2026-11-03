# list direct bl callers (and via xtoc trampolines) of given targets
import sys
from elf import *
T=[int(x,16) for x in sys.argv[1:]]
tramp={}
for a in range(0x10200,0xCC1000,4):
    x=w(a)
    if x>>26==18 and (x&3)==1:
        t=br(a,x)
        tt=t
        if w(t)==0xf8410028 and w(t+12)>>26==18: tt=br(t+12,w(t+12))
        if t in T or tt in T: print('%#x -> %#x (via %#x) in fn %#x'%(a,tt,t,fn(a)))
