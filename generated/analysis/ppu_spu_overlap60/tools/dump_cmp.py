"""Compare two PS3_SAMPLE_DUMP files (overlap60) over the race window.
usage: py -3 dump_cmp.py <dumpA> <dumpB> [t0_ms] [frame_ms_A frame_ms_B]
Columns per function: share of main-thread samples (direct / unwind / scan) in A and B, and, when frame times are
given, ms/frame = share x frame_ms (MODELLED: sampling is periodic, so shares estimate time fractions)."""
import collections
import sys


def load(path, t0):
    d = collections.defaultdict(lambda: [0, 0, 0])
    tot = 0
    t = 0
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == 'T':
            t = int(p[1])
            if t >= t0:
                tot += int(p[3])          # "T <ms> total <n> guest <n>": total samples in the interval
            continue
        if t < t0:
            continue
        g = int(p[0], 16)
        for i in range(3):
            d[g][i] += int(p[1 + i])
    return d, tot


def name(g):
    return 'spu_slot%d_LS_%05X' % ((g >> 18) & 0x1FFF, g & 0x3FFFF) if g & 0x80000000 else 'func_%08X' % g


a, ta = load(sys.argv[1], 0)
t0 = int(sys.argv[3]) if len(sys.argv) > 3 else 42000
a, ta = load(sys.argv[1], t0)
b, tb = load(sys.argv[2], t0)
fa = float(sys.argv[4]) if len(sys.argv) > 5 else None
fb = float(sys.argv[5]) if len(sys.argv) > 5 else None
print('samples A %d  B %d  (t >= %d ms)' % (ta, tb, t0))
for lab, i in (('direct', 0), ('unwind', 1), ('scan', 2)):
    sa = sum(v[i] for v in a.values()); sb = sum(v[i] for v in b.values())
    print('  %-6s A %5.1f%%  B %5.1f%%' % (lab, 100.0 * sa / max(1, ta), 100.0 * sb / max(1, tb)))
keys = sorted(set(a) | set(b), key=lambda g: -(sum(a[g]) / max(1, ta) + sum(b[g]) / max(1, tb)))
hdr = '%-22s %7s %7s %7s | %7s %7s %7s' % ('function', 'A dir%', 'A unw%', 'A scn%', 'B dir%', 'B unw%', 'B scn%')
if fa:
    hdr += ' | %7s %7s %7s' % ('A ms/f', 'B ms/f', 'B-A')
print(hdr)
for g in keys[:40]:
    va, vb = a[g], b[g]
    row = '%-22s %7.2f %7.2f %7.2f | %7.2f %7.2f %7.2f' % (
        name(g), *(100.0 * x / max(1, ta) for x in va), *(100.0 * x / max(1, tb) for x in vb))
    if fa:
        ma = sum(va) / max(1, ta) * fa; mb = sum(vb) / max(1, tb) * fb
        row += ' | %7.2f %7.2f %+7.2f' % (ma, mb, mb - ma)
    print(row)
