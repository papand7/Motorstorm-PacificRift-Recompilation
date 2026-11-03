"""T175: the temporary build's [xs] lines as ns per guest draw and per frame, overhead subtracted. usage: py -3 stage_t175.py <run dir> <GHz of the TSC>"""
import re, sys
from pathlib import Path
from collections import defaultdict
GHZ = float(sys.argv[2])
NAMES = ['begin', 'stream', 'find', 'conv', 'put', 'ixcopy']
rows = defaultdict(list)
for d in sorted(Path(sys.argv[1]).iterdir()):
    a = d.name.rsplit('_', 1)[0]
    L = [l for l in (d / 'err.txt').read_text('utf-8', 'replace').splitlines() if l.startswith('[xs]')]
    if L:
        rows[a].append(L[-1])
OVER = 29  # ticks between the two rdtsc reads of one XS step, measured by tools/rdtsc_t175.c
print(f'{"arm":14s} {"hit":>6s} {"miss":>6s} ' + ' '.join(f'{n:>8s}' for n in NAMES) + '   total  (us per draw; hit, miss per draw)')
for a, ls in sorted(rows.items()):
    tot = defaultdict(float); n = 0; h = m = 0
    for l in ls:
        dr = int(re.search(r'draws=(\d+)', l)[1]); n += dr
        h += int(re.search(r'hit=(\d+)', l)[1]); m += int(re.search(r'miss=(\d+)', l)[1])
        for i, t, o in re.findall(r' (\d)=(\d+)/(\d+)', l):
            tot[int(i)] += max(0, int(t) - OVER * int(o))
    us = [tot[i] / n / GHZ / 1000 for i in range(6)]
    print(f'{a:14s} {h / n:6.0f} {m / n:6.0f} ' + ' '.join(f'{u:8.2f}' for u in us) + f' {sum(us):7.2f}')
