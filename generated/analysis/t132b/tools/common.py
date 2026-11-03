# T132b private helpers: reuse t132 tools
import sys,os
T=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','t132','tools'))
sys.path.insert(0,T)
from elf import *          # retail EBOOT access
import ppcdis as P         # retail range disassembler
def fend(a,limit=0x20000):
    """end of function starting at a: next stdu r1 prologue (after the first 4 insns) or next known start"""
    import bisect
    i=bisect.bisect_right(starts,a); nxt=starts[i] if i<len(starts) else a+limit
    x_a=a+16
    while x_a<a+limit:
        x=w(x_a)
        if (x&0xffff0003)==0xf8210001 :
            # back up over mflr / nops before stdu
            b=x_a
            while w(b-4) in (0x60000000,) or (w(b-4)&0xfc1fffff)==0x7c0802a6: b-=4
            return b
        x_a+=4
    return a+limit
