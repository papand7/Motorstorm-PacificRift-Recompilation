# global code refs to given vtable(s): python vtxref.py VT...
import sys,os
sys.path.insert(0,os.path.dirname(__file__))
from vtrefs import *
from graph import f2
from up import nm
T={int(x,16) for x in sys.argv[1:]}
for f in S:
    if not (0x10200<=f<0xcbdd68): continue
    for x_a,c,n in refs(f):
        if c in T: print('%#x vt %#x %s in %s'%(x_a,c,n,nm(f)[:90]))
