#!/usr/bin/env python3
"""T167: natural experiment over existing logs: 84 ms GPU-wait frames against the RDP session state at each run.

  py -3 rdp_natural_exp_t167.py <session_events.txt> <runs dir> [since YYYYMMDD]

session_events.txt: 'iso-time id ...' lines from TerminalServices-LocalSessionManager (24 = disconnected, 25 = reconnected,
21 = logon, src=LOCAL or a client address); only lines naming session 1. A run counts as connected or disconnected only if the state did not change while it
ran (start plus 200 s). Prints one line per run with [rsx-frame-perf] wait_ms and a table of the two groups."""
import datetime as D, glob, os, re, statistics as S, sys

evs = []
for l in open(sys.argv[1], encoding='utf-8-sig', errors='replace'):
    p = l.split()
    if len(p) >= 2 and p[1] in ('21', '24', '25') and re.search(r'Session ID: *1\b', l):
        evs.append((D.datetime.fromisoformat(p[0]), (p[1] != '24') and ('local' if 'src=LOCAL' in l else 'remote')))
since = sys.argv[3] if len(sys.argv) > 3 else '20261001'
rows = []
for d in sorted(glob.glob(os.path.join(sys.argv[2], '2026*'))):
    n = os.path.basename(d)
    if n[:8] < since or not os.path.exists(d + '/stderr.log'):
        continue
    w, wall = [], []
    for l in open(d + '/stderr.log', errors='replace'):
        if l.startswith('[rsx-frame-perf] gframe='):
            m = re.search(r' wait_ms=([\d.]+)', l)
            if m:
                w.append(float(m.group(1)))
                wall.append(float(re.search(r'wall_ms=([\d.]+)', l).group(1)))
    if len(w) < 100:
        continue
    t0 = D.datetime.strptime(n[:15], '%Y%m%d-%H%M%S')
    t1 = t0 + D.timedelta(seconds=200)
    before = [c for t, c in evs if t <= t0]
    inside = [t for t, c in evs if t0 < t < t1]
    st = 'changed' if inside else (('connected-' + before[-1]) if before and before[-1] else 'disconnected' if before else 'unknown')
    slow = sum(x > 50 for x in w)
    rows.append((st, slow, len(w)))
    print(f'{n[:34]:34s} {st:12s} frames={len(w):5d} wait>50={slow:5d} ({100 * slow / len(w):5.1f}%) wall_p50={S.median(wall):.1f}')
print()
for st in sorted({r[0] for r in rows}):
    g = [r for r in rows if r[0] == st]
    print(f'{st:12s} runs={len(g):3d} with_slow_frames={sum(r[1] > 0 for r in g):3d} frames={sum(r[2] for r in g):7d} slow={sum(r[1] for r in g):7d}')
