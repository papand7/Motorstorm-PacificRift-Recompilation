"""T158: median Havok task entry-run time (kind 39) per image in consecutive time bins of a cpath trace,
to check whether task cost drifts across the race (C1's trace window covers race +0..9.5 s, C0's +7.5..29.5 s).
  py -3 havok_entry_bins_t158.py <cpath.txt> [bin_s]"""
import statistics as S, sys
from collections import defaultdict
IMG = {'145c1b7b': 'solver', '1d51c6ce': 'collide', '1266e45a': 'raycast', '18345147': 'animation'}
binsz = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
b = defaultdict(lambda: defaultdict(list))
for l in open(sys.argv[1], encoding='utf-8', errors='replace'):
    p = l.split()
    if len(p) >= 6 and p[0] == '39' and p[2] in IMG:
        s, e = float(p[4]) / 1e6, float(p[5]) / 1e6
        b[int(s // binsz)][IMG[p[2]]].append((e - s) * 1000)
for k in sorted(b):
    print(f'{k * binsz:6.0f}s', '  '.join(f'{n} {S.median(v):.2f} ms (n={len(v)})' for n, v in sorted(b[k].items())))
