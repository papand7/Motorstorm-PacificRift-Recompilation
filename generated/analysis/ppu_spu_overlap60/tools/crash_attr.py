"""Which main-thread guest functions grow in crash seconds? (overlap60, Kksr113)
usage: py -3 crash_attr.py <cpath trace> <PS3_SAMPLE_DUMP file> [offset_ms]
Per second of the trace: frame time and vehicledeformation SPU-ms (Wws kind 26). Crash seconds = deformation
SPU-ms per second >= 50 (about 1.5 ms per frame; normal play ~2), calm = < 5. The dump's 1 s intervals are matched by
time (dump t ms ~ trace us / 1000 + offset; both clocks start near process start, ~1 s alignment). Output: per
function, ms of main thread per second in crash vs calm seconds (samples x 1000 / samples per second), largest
growth first, split direct (guest code running) vs attributed (runtime code credited to its caller)."""
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'roadto60_next', 'tools'))
from cp77 import module_names   # noqa: E402

trace, dump = sys.argv[1], sys.argv[2]
off = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
names = module_names()
deform = collections.Counter()
frames = collections.defaultdict(list)
flips = []
for line in open(trace, encoding='latin-1'):
    if not line[0].isdigit():
        continue
    p = line.split()
    if len(p) < 6:
        continue
    k = int(p[0])
    if k == 9:
        flips.append(float(p[4]))
    elif k == 26 and names.get(p[2]) == 'vehicledeformation':
        t0, t1 = float(p[4]), float(p[5])
        deform[int(t0 // 1e6)] += (t1 - t0) / 1000.0
flips.sort()
for i in range(len(flips) - 1):
    frames[int(flips[i] // 1e6)].append((flips[i + 1] - flips[i]) / 1000.0)
secs = sorted(frames)
if not secs:
    sys.exit('no frames in the trace')
print('trace seconds %d..%d' % (secs[0], secs[-1]))
for s in secs:
    f = frames[s]
    print('  s=%3d frames %2d mean %5.1f ms max %5.1f | deformation %6.1f SPU-ms' % (s, len(f), sum(f) / len(f), max(f), deform[s]))

# dump intervals: T <ms> total <n> guest <n>, then "<g hex> <direct> <unwind> <scan>"
iv = []
cur = None
for line in open(dump):
    p = line.split()
    if not p:
        continue
    if p[0] == 'T':
        ft = float(p[7]) if len(p) > 7 and p[6] == 'ft_us' else -1.0   # trace clock at the report (step 3 sampler)
        cur = [int(p[1]), int(p[3]), collections.defaultdict(lambda: [0, 0]), ft]
        iv.append(cur)
    elif cur is not None:
        g = int(p[0], 16)
        cur[2][g][0] += int(p[1])
        cur[2][g][1] += int(p[2]) + int(p[3])
crash, calm = [], []
for t_ms, tot, h, ft in iv:
    # the report covers the second before it; with the trace clock, centre it on that second
    s = int((ft / 1000.0 - 500.0) // 1000) if ft >= 0 else int((t_ms - off) // 1000) - 1
    if s not in frames or tot < 100:
        continue
    if deform[s] >= 50:
        crash.append((tot, h))
    elif deform[s] < 5:
        calm.append((tot, h))
print('\nintervals: crash %d, calm %d' % (len(crash), len(calm)))
if not crash or not calm:
    sys.exit('not enough crash or calm seconds to compare')


def ms_per_s(group):
    out = collections.defaultdict(lambda: [0.0, 0.0])
    for tot, h in group:
        for g, (d, a) in h.items():
            out[g][0] += 1000.0 * d / tot / len(group)
            out[g][1] += 1000.0 * a / tot / len(group)
    return out


cr, ca = ms_per_s(crash), ms_per_s(calm)
rows = []
for g in set(cr) | set(ca):
    rows.append((sum(cr[g]) - sum(ca[g]), g))
rows.sort(reverse=True)
print('%-14s %9s %9s %9s | %8s %8s' % ('function', 'calm ms/s', 'crash', 'growth', 'crash dir', 'crash att'))
for dlt, g in rows[:30]:
    nm = ('spu_%05X' % (g & 0x3FFFF)) if g & 0x80000000 else 'func_%08X' % g
    print('%-14s %9.1f %9.1f %+9.1f | %8.1f %8.1f' % (nm, sum(ca[g]), sum(cr[g]), dlt, cr[g][0], cr[g][1]))
