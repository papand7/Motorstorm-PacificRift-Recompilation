"""T174: per arm, median upload units per frame (last 20 frames, 256 bytes each) and the last [vp-indexed] counters. usage: py -3 bytes_t174.py <run dir>"""
import re, statistics as st, sys
from collections import defaultdict
from pathlib import Path

u, ix, wall = defaultdict(list), {}, defaultdict(list)
for d in sorted(Path(sys.argv[1]).iterdir()):
    a = d.name.rsplit('_', 1)[0]
    log = (d / 'err.txt').read_text('utf-8', 'replace').splitlines()
    v = [int(m[1]) for l in log if l.startswith('[rsx-frame-perf]') and (m := re.search(r'\bverts=(\d+)', l))]
    u[a] += v[-20:]
    n = [l for l in log if l.startswith('[vp-indexed] draws')]
    if n:
        ix[a] = n[-1]
    if (d / 'rc').read_text().strip() != '0':
        print('NONZERO RC', d.name)
for a in sorted(u):
    m = st.median(u[a]) if u[a] else 0
    print(f'{a:12s} upload {m * 256 / 1048576:7.1f} MB/frame  {ix.get(a, "")}')
