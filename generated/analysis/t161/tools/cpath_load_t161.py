#!/usr/bin/env python3
"""T161 V2: host-thread CPU (kind 32, a = run-time us from cycle counts) and async SPU task busy time
(kind 34) per load phase from cpath.txt.  py -3 cpath_load_t161.py <cpath.txt> name:lo:hi ...
Prints, per phase, each host slot's CPU cores (cpu us / wall us) and SPU-task busy cores. CPU, not elapsed."""
import sys
from collections import defaultdict
names, cpu, spu = {}, [], []
for l in open(sys.argv[1], encoding='utf-8', errors='replace'):
    p = l.split()
    if not p: continue
    if p[0] == 'H': names[int(p[1])] = ' '.join(p[5:]); continue
    if p[0] == '32': cpu.append((int(p[1]), int(p[2], 16), float(p[4]) / 1e6, float(p[5]) / 1e6))
    elif p[0] == '34': spu.append((float(p[4]) / 1e6, float(p[5]) / 1e6))
for ph in sys.argv[2:]:
    n, lo, hi = ph.split(':'); lo, hi = float(lo), float(hi)
    per = defaultdict(float)
    for slot, a, t0, t1 in cpu:
        ov = min(t1, hi) - max(t0, lo)
        if ov > 0 and t1 > t0: per[slot] += a / 1e6 * ov / (t1 - t0)
    busy = sum(max(0.0, min(b, hi) - max(a, lo)) for a, b in spu)
    w = hi - lo
    top = sorted(per.items(), key=lambda kv: -kv[1])[:6]
    print(f'{n} [{lo}-{hi}] total {sum(per.values())/w:.2f} cores; spu tasks {busy/w:.2f};',
          ', '.join(f'{names.get(s, s)} {v/w:.2f}' for s, v in top))
