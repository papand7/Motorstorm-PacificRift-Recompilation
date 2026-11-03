#!/usr/bin/env python3
"""T161: per-thread [hle-wait] imports and [lwc] lwcond aggregates per phase (host s), all threads.
py -3 lwc_tids_t161.py <run_dir> <ps3recomp_dir> name:lo:hi ...   prints text"""
import re, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from lwc_t161 import HB, LWC, HW, KEY, names
rd, pr, phases = sys.argv[1], sys.argv[2], sys.argv[3:]
nm = names(pr)
host_s, hw, lwc = 0.0, [], []
for l in open(Path(rd) / 'stderr.log', encoding='utf-8', errors='replace'):
    if l.startswith('[rsx-hb]'):
        m = HB.match(l); host_s = int(m.group(1)) / 1000.0 if m else host_s
    elif l.startswith('[hle-wait]'):
        m = HW.match(l)
        if m: hw.append((host_s, int(m.group(1)), KEY.findall(m.group(2))))
    elif l.startswith('[lwc] '):
        m = LWC.match(l)
        if m: lwc.append((host_s, int(m.group(2)), m.group(3), m.group(5), int(m.group(6)), float(m.group(7)), int(m.group(8))))
for ph in phases:
    n, lo, hi = ph.split(':'); lo, hi = float(lo), float(hi)
    print(f'## {n} {lo}-{hi} ({hi-lo:.2f} s)')
    a = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
    for t, tid, keys in hw:
        if lo <= t < hi:
            for nid, ms, c in keys:
                x = a[tid][nm(nid)]; x[0] += int(c); x[1] += float(ms)
    b = defaultdict(lambda: [0, 0.0, 0])
    for t, tid, cv, lr, c, w, e in lwc:
        if lo <= t < hi:
            x = b[(tid, cv, lr)]; x[0] += c; x[1] += w; x[2] += e
    for tid in sorted(a):
        tot = sum(v[1] for v in a[tid].values())
        top = sorted(a[tid].items(), key=lambda kv: -kv[1][1])[:4]
        print(f' tid {tid:3d} {tot/1e3/(hi-lo)*100:5.1f}% ' + ' '.join(f'{k}={v[1]/1e3:.2f}s/{v[0]}' for k, v in top))
    for k, v in sorted(b.items(), key=lambda kv: -kv[1][1])[:12]:
        print(f'  lwc tid {k[0]:3d} cv={k[1]} lr={k[2]} calls={v[0]} wait={v[1]/1e3:.2f}s eps={v[2]}')
