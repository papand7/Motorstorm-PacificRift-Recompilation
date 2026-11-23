"""Summarize each ExecuteFunction signature case in dispatcher 0x59DC60 (jump table 0x59DE44)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import *
JT = 0x59DE44
cases = []
for i in range(25):
    w = rd(JT + 4 * i); w = w - (1 << 32) if w & 0x80000000 else w
    cases.append((i, JT + w))
NAMES = {0x785c68: 'std::string(char*)', 0x6fa700: 'stricmp("TRUE")', 0x6fd5a0: 'strtol', 0x6fc350: 'strtod',
         0x9C5D10: 'ret=bool', 0x7856b8: 'ret=std::string', 0x73dad0: 'free', 0x6f9a20: 'strcpy', 0x58A428: 'alloc(ret holder)'}
for i, s in cases:
    out = []; a = s
    for k in range(80):
        w = rd(a); op = w >> 26
        if op == 18:
            li = w & 0x3fffffc
            if li & 0x2000000: li -= 0x4000000
            t = a + li; tr = tramp(t); tt = tr[0] if tr else t
            if w & 1: out.append(NAMES.get(tt, hex(tt)))
            elif tt == 0x59DCE0: break
        if w in (0x4E800421, 0x4E800021): out.append('CALL')
        if op == 36 and (w >> 16) & 31 == 26 and (w & 0xffff) == 0:  # stw rX,0(r26) -> kind
            out.append('kind<-r%d' % ((w >> 21) & 31))
        if op == 14 and (w >> 16) & 31 == 0 and (w >> 21) & 31 in (11, 30, 5, 6, 9, 0, 3, 4, 7, 8, 10, 12):
            pass
        if op == 52 and (w >> 16) & 31 in (6, 9, 3):  # stfs to holder
            out.append('stfs(float ret)')
        a += 4
    print(i, hex(s), ' '.join(out))
