#!/usr/bin/env python3
"""T161: shader/PSO compile time per run from [rsx-frame-perf] (py -3 pso_miss_t161.py <run_dir>...).
Sums the vertex-program miss (`vs=a/b miss_ms`) and PSO miss (`pso ... miss=N miss_ms`) per pass,
split at race frame 0 (first frame with >= 200 draws): what a warm persistent shader/PSO cache
(RSX_SHADER_CACHE=2/3) could remove at most."""
import json, re, sys
from pathlib import Path

PF = re.compile(r'\[rsx-frame-perf\] gframe=(\d+) .*?draw_calls=(\d+).*?vs=\S+ miss_ms=([\d.]+).*?'
                r'pso [\d.]+ n=\d+ miss=(\d+) miss_ms=([\d.]+)')

def one(rd):
    tot = {'pre': [0.0, 0.0, 0], 'race': [0.0, 0.0, 0]}
    race = False
    with open(Path(rd) / 'stderr.log', encoding='utf-8', errors='replace') as f:
        for line in f:
            if not line.startswith('[rsx-frame-perf] gframe='):
                continue
            m = PF.search(line)
            if not m:
                continue
            if int(m.group(2)) >= 200:
                race = True
            t = tot['race' if race else 'pre']
            t[0] += float(m.group(3)); t[1] += float(m.group(5)); t[2] += int(m.group(4))
    return {k: {'vp_miss_ms': round(v[0], 1), 'pso_miss_ms': round(v[1], 1), 'pso_misses': v[2]}
            for k, v in tot.items()}

print(json.dumps({Path(rd).name: one(rd) for rd in sys.argv[1:]}, indent=1))
