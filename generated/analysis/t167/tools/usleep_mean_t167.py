#!/usr/bin/env python3
"""T167: mean per-call duration of sys_timer_usleep (sc141) by 20 s window, all guest threads, from [sc-wait] lines.
  py -3 usleep_mean_t167.py <run_dir> [...]"""
import re, sys
from collections import defaultdict
from pathlib import Path
for run in sys.argv[1:]:
    ms, n, t = defaultdict(float), defaultdict(int), 0.0
    for l in (Path(run) / 'stderr.log').open(encoding='utf-8', errors='replace'):
        if l.startswith('[rsx-hb]'):
            t = int(re.search(r'ms=(\d+)', l).group(1)) / 1000.0
        elif l.startswith('[sc-wait]'):
            m = re.search(r'sc141=([\d.]+)ms/(\d+)', l)
            if m:
                ms[int(t // 20)] += float(m.group(1))
                n[int(t // 20)] += int(m.group(2))
    print(Path(run).name, ' '.join(f'{k * 20}s:{ms[k] / n[k]:.2f}ms/{n[k]}' for k in sorted(n)))
