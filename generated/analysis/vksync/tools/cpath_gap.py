"""Events in a window of one frame of a critical-path trace (PS3_CRITICAL_PATH_TRACE).

usage: py -3 cpath_gap.py <cpath.txt> <frame#> <from_ms> <to_ms> [per_kind=12]
Frame n starts at the n-th flip request (kind 9). CPU samples (32) are left out, and so are
long blocking spans of threads other than the frame thread (tid 1)."""
import collections
import sys

path, frame, a_ms, b_ms = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
per = int(sys.argv[5]) if len(sys.argv) > 5 else 12
ev = []
names = {}
for line in open(path):
    p = line.split()
    if p and p[0] == 'H':
        names[p[1]] = ' '.join(p[3:])
    if len(p) < 6 or p[0] in ('T', 'H', '#', '32'):
        continue
    ev.append((float(p[4]), float(p[5]), p))
ev.sort(key=lambda x: x[0])
fl, t0, seen = 0, None, collections.Counter()
for s, e, p in ev:
    if p[0] == '9':
        fl += 1
        if fl == frame:
            t0 = s
    if fl != frame or s < t0 + a_ms * 1000 or s > t0 + b_ms * 1000:
        continue
    if p[0] in ('1', '2') and p[1] != '1' and e - s > 5000:
        continue
    seen[p[0]] += 1
    if seen[p[0]] > per:
        continue
    print('%8.2f %7.2f  %s' % ((s - t0) / 1000, (e - s) / 1000, ' '.join(p[:4])))
print('counts by kind:', dict(seen))
