"""T158: summarise hvkdiff bench logs per image: per-seed ratios, mean and range (markdown rows).
  py -3 hvk_bench_table.py <bench log> [label0] [label1]"""
import re
import statistics as S
import sys
from collections import defaultdict

log = open(sys.argv[1], encoding='utf-8').read()
a0, a1 = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ('C0', 'C1')
rows = defaultdict(list)
for blk in re.split(r'^== ', log, flags=re.M)[1:]:
    img = blk.split()[0]
    t = re.search(r'^time C0 ([\d.]+) ms C1 ([\d.]+) ms ratio ([\d.]+) \| ns per SPU instruction C0 ([\d.]+) C1 ([\d.]+)', blk, re.M)
    l = re.search(r'^long cases.*?C0 ([\d.]+) ms C1 ([\d.]+) ms ratio ([\d.]+) \| ns per SPU instruction C0 ([\d.]+) C1 ([\d.]+)', blk, re.M)
    if t:
        rows[img].append((t, l))
print(f'| Image | seeds | {a0} ns/SPU insn | {a1} ns/SPU insn | {a1}/{a0} time (mean, range) | long cases {a1}/{a0} (mean, range) |')
print('|---|---|---|---|---|---|')
for img, v in rows.items():
    r = [float(t[3]) for t, _ in v]
    n0 = [float(t[4]) for t, _ in v]
    n1 = [float(t[5]) for t, _ in v]
    lr = [float(l[3]) for _, l in v if l]
    ls = f'{S.mean(lr):.3f} ({min(lr):.3f}-{max(lr):.3f})' if lr else 'none'
    print(f'| {img} | {len(v)} | {S.mean(n0):.3f} | {S.mean(n1):.3f} | {S.mean(r):.3f} ({min(r):.3f}-{max(r):.3f}) | {ls} |')
