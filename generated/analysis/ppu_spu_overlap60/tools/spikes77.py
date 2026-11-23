"""Long frames in the Kksr77 critical-path trace: where does the extra time go?
usage: py -3 spikes77.py <trace> [threshold_ms]
Frames = flip to flip (kind 9). Main-thread time per frame split into: JobBatch wait (usleep lr 94cca8), Havok/physics
semaphore (sc 0x82), GcKernel poll (usleep lr 72e5c0), Havok polls, other main usleeps by lr, and compute (rest).
Also SPU work per module overlapping the frame (Wws kind 26 by module key, Havok kind 39)."""
import bisect
import collections
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'roadto60_next', 'tools'))
from cp77 import module_names, HAVOK   # noqa: E402

path = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 45.0
thr_hi = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9   # upper bound: leave out the wheel-scan stalls
names = module_names()
flips, waits, jobs = [], [], []
for line in open(path, encoding='latin-1'):
    if not line[0].isdigit():
        continue
    p = line.split()
    if len(p) < 6:
        continue
    k, who, a, b, t0, t1 = int(p[0]), p[1], p[2], p[3], float(p[4]), float(p[5])
    if k == 9:
        flips.append(t0)
    elif k == 2 and who == '1':
        lab = {'94cca8': 'jobbatch', '72e5c0': 'gckernel', 'a49ad4': 'havok_poll', 'a48b4c': 'havok_poll',
               'a48364': 'havok_poll'}.get(b, 'usleep_' + b)
        waits.append((t0, t1, lab))
    elif k == 1 and who == '1' and t1 - t0 >= 20:
        waits.append((t0, t1, 'sem' if a == '82' else 'sc_' + a))
    elif k == 26:
        jobs.append((t0, t1, names.get(a, a)))
    elif k == 39:
        jobs.append((t0, t1, HAVOK.get(a, a)))
flips.sort(); waits.sort(); jobs.sort()
ws = [w[0] for w in waits]
js = [j[0] for j in jobs]


def frame(f0, f1):
    d = collections.Counter()
    lo = bisect.bisect_left(ws, f0 - 200000)
    hi = bisect.bisect_right(ws, f1)
    for w0, w1, lab in waits[lo:hi]:
        o = min(w1, f1) - max(w0, f0)
        if o > 0:
            d[lab] += o / 1000.0
    d['compute'] = (f1 - f0) / 1000.0 - sum(d.values())
    s = collections.Counter()
    lo = bisect.bisect_left(js, f0 - 200000)
    hi = bisect.bisect_right(js, f1)
    for j0, j1, mod in jobs[lo:hi]:
        o = min(j1, f1) - max(j0, f0)
        if o > 0:
            s[mod] += o / 1000.0
    return d, s


fr = [(flips[i], flips[i + 1]) for i in range(len(flips) - 1)]
dur = [(b - a) / 1000.0 for a, b in fr]
med = st.median(dur)
longf = [i for i, x in enumerate(dur) if thr <= x < thr_hi]
print('frames %d, median %.1f ms, p90 %.1f, p99 %.1f, max %.1f; >= %.0f ms: %d (%.1f%%)' % (
    len(dur), med, sorted(dur)[int(len(dur) * .9)], sorted(dur)[int(len(dur) * .99)], max(dur), thr, len(longf),
    100.0 * len(longf) / len(dur)))
normal = [i for i, x in enumerate(dur) if abs(x - med) < 2.0]
agg_n, agg_l = collections.Counter(), collections.Counter()
spu_n, spu_l = collections.Counter(), collections.Counter()
for i in normal:
    d, s = frame(*fr[i]); agg_n.update(d); spu_n.update(s)
for i in longf:
    d, s = frame(*fr[i]); agg_l.update(d); spu_l.update(s)
nn, nl = max(1, len(normal)), max(1, len(longf))
print('\nmain thread, ms per frame: normal (%d frames, median +-2 ms) vs long (%d frames)' % (len(normal), len(longf)))
for lab in sorted(set(agg_n) | set(agg_l), key=lambda x: -(agg_l[x] / nl - agg_n[x] / nn)):
    a, b = agg_n[lab] / nn, agg_l[lab] / nl
    if max(a, b) >= 0.2:
        print('  %-18s %6.2f %6.2f  %+6.2f' % (lab, a, b, b - a))
print('\nSPU work overlapping the frame, SPU-ms per frame: normal vs long')
for mod in sorted(set(spu_n) | set(spu_l), key=lambda x: -(spu_l[x] / nl - spu_n[x] / nn))[:14]:
    a, b = spu_n[mod] / nn, spu_l[mod] / nl
    print('  %-24s %6.2f %6.2f  %+6.2f' % (mod, a, b, b - a))
print('\nlongest 12 frames:')
for i in sorted(longf, key=lambda i: -dur[i])[:12]:
    d, s = frame(*fr[i])
    top = ', '.join('%s %.1f' % (k, v) for k, v in d.most_common(4))
    tops = ', '.join('%s %.1f' % (k, v) for k, v in s.most_common(3))
    print('  #%d t=%.1fs %.1f ms | %s | SPU: %s' % (i, (fr[i][0] - flips[0]) / 1e6, dur[i], top, tops))
gaps = [longf[i + 1] - longf[i] for i in range(len(longf) - 1)]
if gaps:
    print('\nspacing between long frames (frames): median %d, min %d, max %d' % (st.median(gaps), min(gaps), max(gaps)))
