"""Extract GUI ExecuteFunction registrations from init 0x19CB0 by simple register/stack tracking.
Output: name, OPD, entry, wrapper, GUI register fn, map offset.  usage: py -3 regtable.py [filter]"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
from common import *
WR = {}
for v in range(0x1E6620, 0x1E6E09, 0x58):
    w = rd(v + 0x38); li = w & 0x3fffffc
    if li & 0x2000000: li -= 0x4000000
    t = tramp(v + 0x38 + li)
    if not t: continue
    g = t[0]; hi = lo = 0
    for x in range(g, g + 0x40, 4):
        ww = rd(x)
        if ww >> 26 == 15 and (ww >> 21) & 31 == 3 and (ww >> 16) & 31 == 3: hi = s16(ww & 0xffff)
        if ww >> 26 == 14 and (ww >> 21) & 31 == 3 and (ww >> 16) & 31 == 3: lo = s16(ww & 0xffff)
    WR[v] = (g, hi * 65536 + lo)
reg = {}; stk = {}
out = []
S, E = 0x19CB0, 0x2A978
for a in range(S, E, 4):
    w = rd(a); op = w >> 26; rt = (w >> 21) & 31; ra = (w >> 16) & 31; im = s16(w & 0xffff)
    if op == 32 and ra == 2:  # lwz rt, im(r2)
        reg[rt] = ('v', rd((TOC + im) & 0xffffffff))
    elif op == 14 and ra == 1:  # addi rt, r1, im
        reg[rt] = ('sp', im)
    elif op == 14 and ra == 0:
        reg[rt] = ('v', im & 0xffffffff)
    elif op in (36, 62) and ra == 1:  # stw/std rt, im(r1)
        if op == 62: im &= ~3
        stk[im] = reg.get(rt)
        if op == 62 and reg.get(rt) and reg[rt][0] == 'sp': pass
    elif op in (32, 58) and ra == 1:  # lwz/ld rt, im(r1)
        if op == 58: im &= ~3
        reg[rt] = stk.get(im)
    elif op == 31 and ((w >> 1) & 0x3ff) == 444 and ((w >> 11) & 31) == rt:  # or ra, rt, rt (mr)
        reg[ra] = reg.get(rt)
    elif op == 30 and ((w >> 2) & 7) == 0 and ((w >> 11) & 31) == 0:  # rldicl ra, rs, 0, 32
        reg[ra] = reg.get(rt)
    elif op == 18 and (w & 1):
        li = w & 0x3fffffc
        if li & 0x2000000: li -= 0x4000000
        t = a + li
        if t in WR:
            name = reg.get(4); fp = reg.get(5)
            nm = cstr(name[1]) if name and name[0] == 'v' else None
            opd = None
            if fp and fp[0] == 'sp':
                x = stk.get(fp[1] + 4)
                opd = x[1] if x and x[0] == 'v' else None
            ent = rd(opd) if opd else None
            out.append((a, nm, opd, ent, t, WR[t][0], WR[t][1]))
        for r in (0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12): reg.pop(r, None)
flt = re.compile(sys.argv[1]) if len(sys.argv) > 1 else None
for a, nm, opd, ent, t, g, mo in out:
    line = f'{a:06X} {str(nm):40s} opd={opd and hex(opd)} entry={ent and hex(ent)} wrap={t:#x} reg={g:#x} map=mgr+{mo:#x}'
    if not flt or flt.search(line): print(line)
print('total', len(out), 'unresolved', sum(1 for o in out if not o[1] or not o[2]), file=sys.stderr)
