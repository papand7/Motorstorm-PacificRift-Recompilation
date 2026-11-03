"""T79: find direct b/bl sites (I-form) to a target in the retail EBOOT, and TOC-switch stubs
(std r2,0x28(r1); addis r2; addi r2; b target) plus their callers. Read-only.
Usage: py -3 -I branch_xref.py <EBOOT.elf> <hex target> [...]"""
import struct, sys
d = open(sys.argv[1], 'rb').read()
phoff = struct.unpack('>Q', d[0x20:0x28])[0]; n = struct.unpack('>H', d[0x38:0x3a])[0]
segs = []
for i in range(n):
    p = struct.unpack('>IIQQQQQQ', d[phoff+i*56:phoff+i*56+56])
    if p[0] == 1 and p[1] & 1: segs.append((p[3], p[2], p[5]))
def words():
    for va, off, sz in segs:
        for o in range(0, sz - 3, 4):
            yield va + o, struct.unpack('>I', d[off+o:off+o+4])[0]
W = dict(words())
def targ(a, w):
    if w >> 26 != 18: return None
    li = w & 0x03FFFFFC
    if li & 0x02000000: li -= 0x04000000
    return (li if w & 2 else a + li) & 0xFFFFFFFF, w & 1
def sites(t):
    return [(a, l) for a, w in W.items() if (r := targ(a, w)) and r[0] == t for l in [r[1]]]
for ts in sys.argv[2:]:
    t = int(ts, 16)
    print(f'target {t:#x}')
    for a, l in sorted(sites(t)):
        kind = 'bl' if l else 'b '
        stub = ''
        if not l and W.get(a-12) == 0xF8410028:
            s = a - 12
            callers = sorted(x for x, ll in sites(s) if ll)
            stub = f' TOC stub @ {s:#x}, bl callers: ' + ', '.join(hex(c) for c in callers)
        print(f'  {kind} at {a:#x}{stub}')
