"""T178: per-phase, per-thread waits of one run from [hle-wait]/[sc-wait]/[spurs-sched]/[lwc-wake] windows, clocked by [rsx-hb].
usage: py -3 phase_waits_t178.py <stderr.log> <label:from_s:to_s> ..."""
import re, sys
from collections import defaultdict
L = open(sys.argv[1], encoding='utf-8', errors='replace').read().splitlines()
ph = [(a.split(':')[0], float(a.split(':')[1]), float(a.split(':')[2])) for a in sys.argv[2:]]
now = 0.0
rows = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
sched = defaultdict(lambda: defaultdict(float))
RE = re.compile(r'(nid[0-9A-F]+|sc\d+)=([0-9.]+)ms/(\d+)')
for l in L:
    m = re.match(r'\[rsx-hb\].*?\bms=(\d+)', l)
    if m:
        now = int(m[1]) / 1000
        continue
    p = next((n for n, a, b in ph if a <= now < b), None)
    if not p:
        continue
    m = re.match(r'\[(hle|sc)-wait\] window_ms=\d+ tid=(\d+)', l)
    if m:
        for k, ms, n in RE.findall(l):
            r = rows[p][(int(m[2]), k)]
            r[0] += float(ms); r[1] += int(n)
    elif l.startswith('[spurs-sched]') and 'workers_mcyc' in l:
        for k in ('wakes/s', 'productive', 'hook_commits', 'worker_wakes', 'pass_us', 'workers_mcyc', 'coord_mcyc'):
            mm = re.search(re.escape(k) + r'=([0-9.]+)', l)
            if mm: sched[p][k] += float(mm[1])
for n, a, b in ph:
    print(f'== {n} {a}-{b} ({b-a:.1f}s)')
    print('  sched', {k: round(v) for k, v in sched[n].items()})
    per = defaultdict(list)
    for (t, k), (ms, c) in rows[n].items():
        if ms >= 5: per[t].append((ms, k, c))
    for t in [x for x in (1, 6, 9, 14, 15, 19) if x in per]:
        print(f'  tid {t:3d}', ' '.join(f'{k}={ms/1000:.2f}s/{c}' for ms, k, c in sorted(per[t], reverse=True)[:8]))
