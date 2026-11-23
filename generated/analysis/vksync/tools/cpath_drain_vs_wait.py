"""Per frame of a critical-path trace: when the frame thread's long reference wait (usleep run at
guest lr 0x72E5C0, func_0072E1E0) starts, when the frame's long drain pass(es) run, and the flip.

usage: py -3 cpath_drain_vs_wait.py <cpath.txt> [min_drain_ms=2]
Columns (ms from the frame's flip request): wait start, wait length, first long drain start,
summed long-drain time, frame length. Summary: medians, and how often the drain began after the wait."""
import statistics
import sys

path = sys.argv[1]
min_drain = float(sys.argv[2]) * 1000 if len(sys.argv) > 2 else 2000.0
ev = []
for line in open(path):
    p = line.split()
    if len(p) < 6 or p[0] not in ('2', '7', '9'):
        continue
    ev.append((float(p[4]), float(p[5]), p))
ev.sort(key=lambda x: x[0])
flips = [s for s, e, p in ev if p[0] == '9']
rows = []
for i in range(len(flips) - 1):
    f0, f1 = flips[i], flips[i + 1]
    waits = [(s, e) for s, e, p in ev if p[0] == '2' and p[1] == '1' and p[3] == '72e5c0' and f0 <= s < f1]
    drains = [(s, e) for s, e, p in ev if p[0] == '7' and f0 <= s < f1 and e - s >= min_drain]
    if not waits or not drains:
        continue
    w0, w1 = waits[0]
    rows.append(((w0 - f0) / 1000, (w1 - w0) / 1000, (drains[0][0] - f0) / 1000,
                 sum(e - s for s, e in drains) / 1000, (f1 - f0) / 1000))
for r in rows[:12]:
    print('wait@%6.1f len %5.1f | drain@%6.1f sum %5.1f | frame %5.1f' % r)
if rows:
    med = [statistics.median(c) for c in zip(*rows)]
    late = sum(1 for r in rows if r[2] > r[0])
    print('frames %d; medians: wait@%.1f len %.1f | drain@%.1f sum %.1f | frame %.1f'
          % (len(rows), *med))
    print('drain began after the wait in %d of %d frames; gap (drain - wait) median %.1f ms'
          % (late, len(rows), statistics.median(r[2] - r[0] for r in rows)))
