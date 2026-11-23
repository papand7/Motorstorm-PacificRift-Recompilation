"""resolve registered OPD -> PMF thunk -> real member function entry. usage: py -3 thunk.py <name regex>"""
import sys, os, re, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from common import *
def real(entry):
    w = rd(entry)
    if w >> 26 == 32 and (w >> 16) & 31 == 2:
        p = rd((TOC + s16(w & 0xffff)) & 0xffffffff)
        if p & 1: return ('virtual', p - 1)
        return ('direct', rd(p), p)
    return None
if __name__ == '__main__':
    for line in open(os.path.join(os.path.dirname(__file__), '..', 'regtable.txt')):
        if re.search(sys.argv[1], line):
            ent = int(re.search(r'entry=(0x[0-9a-f]+)', line).group(1), 16)
            r = real(ent)
            print(line.split()[1], hex(ent), r and tuple(hex(x) if isinstance(x, int) else x for x in r), re.search(r'map=\S+', line).group(0))
