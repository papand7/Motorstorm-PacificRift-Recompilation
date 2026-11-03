#!/usr/bin/env python3
"""T167: SPURS kernel iterations per 10 s window across runs, from logs. Shows when a run's rate collapses.
  py -3 spurs_rate_t167.py <run_dir> [...]"""
import re, sys
from collections import Counter
from pathlib import Path
for run in sys.argv[1:]:
    c, t = Counter(), 0.0
    p = Path(run) / 'stderr.log'
    if not p.exists():
        continue
    for l in p.open(encoding='utf-8', errors='replace'):
        if l.startswith('[rsx-hb]'):
            t = int(re.search(r'ms=(\d+)', l).group(1)) / 1000.0
        elif l.startswith('[spurs-busy]'):
            m = re.search(r'runs=(\d+)', l)
            if m:
                c[int(t // 10)] += int(m.group(1))
    print(Path(run).name, ' '.join(f'{c[k]}' for k in range(0, 22)))
