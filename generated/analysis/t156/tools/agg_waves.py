"""T156: aggregate bench_waves runs (logs/bench_waves*.txt) per configuration: mean and sample sd over
the repeated runs of each run's own statistic (p50/p95 of a 200-frame run).

  py -3 agg_waves.py logs/bench_waves.txt
"""
import re
import statistics as S
import sys
from collections import defaultdict

rows = defaultdict(lambda: defaultdict(list))
cfg = None
for line in open(sys.argv[1], encoding='utf-8'):
    m = re.match(r'mode (\S+), frames \d+, load threads (\d+), PPU gap (\d+) us(?:, prologue (\d))?', line)
    if m:
        cfg = (int(m.group(2)), int(m.group(3)), m.group(1))
        continue
    m = re.match(r'\s+(.+?)\s+mean\s+(\S+)\s+p50\s+(\S+)\s+p95\s+(\S+)\s+p99\s+(\S+)', line)
    if m and cfg:
        name = m.group(1).strip()
        for k, v in zip(('mean', 'p50', 'p95', 'p99'), m.groups()[1:]):
            rows[cfg][(name, k)].append(float(v))

METRICS = [('chain (w1 submit->w3 end)', 'p50'), ('chain (w1 submit->w3 end)', 'p95'),
           ('chain (w1 submit->w3 end)', 'p99'), ('wave 1 span', 'p50'), ('wave 2 span', 'p50'),
           ('wave 3 span', 'p50'), ('wave 1 start spread', 'p50'), ('dispatch latency us', 'p50'),
           ('dispatch latency us', 'p95'), ('PPU cost per submit us', 'p50'), ('PPU cost per submit us', 'p95'),
           ('exit -> PPU sees us', 'p50'), ('process CPU ms/frame', 'mean')]


def fmt(v):
    if not v:
        return '-'
    sd = S.stdev(v) if len(v) > 1 else 0.0
    return f'{S.mean(v):.3f} ± {sd:.3f}'


for load in sorted({c[0] for c in rows}):
    for gap in sorted({c[1] for c in rows if c[0] == load}):
        t, p = rows.get((load, gap, 'thread-per-task')), rows.get((load, gap, 'pool'))
        n = len(next(iter(t.values()))) if t else 0
        print(f'\n### load threads {load}, PPU gap {gap} us ({n} runs x 200 frames; ms unless noted)\n')
        print('| metric | thread per task | pool | delta |')
        print('|---|---|---|---|')
        for name, k in METRICS:
            a, b = (t or {}).get((name, k), []), (p or {}).get((name, k), [])
            d = f'{S.mean(b) - S.mean(a):+.3f}' if a and b else '-'
            print(f'| {name} {k} | {fmt(a)} | {fmt(b)} | {d} |')
