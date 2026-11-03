"""T107: function start (backward scan for 'stdu r1') and direct bl callers
of each target: t107_xref.py <elf> <va_hex>..."""
import struct, sys
b = open(sys.argv[1], 'rb').read()
phoff = struct.unpack('>Q', b[0x20:0x28])[0]; n = struct.unpack('>H', b[0x38:0x3a])[0]
segs = []
for i in range(n):
    o = phoff + i * 0x38
    t, fl, off, va, pa, fsz = struct.unpack('>IIQQQQ', b[o:o+0x28])
    if t == 1 and fl & 1: segs.append((off, va, fsz))
def word(a):
    for off, va, fsz in segs:
        if va <= a < va + fsz: return struct.unpack('>I', b[off+a-va:off+a-va+4])[0]
def fstart(a):
    while a > 0:
        w = word(a)
        if w is not None and (w & 0xFFFF0000) == 0xF8210000 and (w & 3) == 1: return a   # stdu r1,-x(r1)
        a -= 4
for t in [int(x, 16) for x in sys.argv[2:]]:
    f = fstart(t)
    callers = []
    for off, va, fsz in segs:
        for i in range(0, fsz, 4):
            w = struct.unpack('>I', b[off+i:off+i+4])[0]
            if (w >> 26) == 18 and (w & 3) == 1:
                d = w & 0x03FFFFFC
                if d & 0x02000000: d -= 0x04000000
                if va + i + d == f: callers.append(va + i)
    print('0x%X in func 0x%X (stdu); callers: %s' % (t, f, ' '.join('0x%X' % c for c in callers[:20])))
