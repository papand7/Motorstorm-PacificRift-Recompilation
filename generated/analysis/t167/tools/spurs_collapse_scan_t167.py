#!/usr/bin/env python3
"""T167: every run since a date whose [spurs-busy] rate collapses: a 10 s window under a third of the run's median over the first 110 s,
with the race not yet entered (windows after 110 s, rate before draws rise). Logs only.
  py -3 spurs_collapse_scan_t167.py <runs_dir> <since YYYYMMDD>"""
import re, statistics as S, sys
from collections import Counter
from pathlib import Path
hits = n = 0
for d in sorted(Path(sys.argv[1]).iterdir()):
    p = d / 'stderr.log'
    if d.name[:8] < sys.argv[2] or not p.exists():
        continue
    c, t, last = Counter(), 0.0, 0.0
    for l in p.open(encoding='utf-8', errors='replace'):
        if l.startswith('[rsx-hb]'):
            t = last = int(re.search(r'ms=(\d+)', l).group(1)) / 1000.0
        elif l.startswith('[spurs-busy]'):
            m = re.search(r'runs=(\d+)', l)
            if m:
                c[int(t // 10)] += int(m.group(1))
    full = [k for k in range(int(last // 10)) if k in c]
    if len(full) < 4:
        continue
    n += 1
    med = S.median(c[k] for k in full[:8])
    low = [k * 10 for k in full if c[k] < med / 3]
    if low:
        hits += 1
        print(d.name, 'median', med, 'low windows s', low[:8], 'min', min(c[k] for k in full))
print('runs', n, 'with a collapse', hits)
