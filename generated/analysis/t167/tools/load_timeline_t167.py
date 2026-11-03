#!/usr/bin/env python3
"""T167: per-window load timeline of one run from its stderr.log (logs only, no game).
  py -3 load_timeline_t167.py <run_dir> [window_s]
Line order is the clock: [spurs-busy] and [sc-wait] carry no time, so each belongs to the window of the last [rsx-hb] ms= seen.
Prints, per window: frames, 0x536A30 enter count and exit-duration sum, SPURS runs and busy ms, main-thread wait by syscall."""
import re, sys
from collections import Counter, defaultdict
from pathlib import Path

run, W = Path(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
w = defaultdict(lambda: dict(fr=0, ent=0, dur=0.0, runs=0, busy=0.0, sc=Counter(), n=0))
t = 0.0
for l in (run / 'stderr.log').open(encoding='utf-8', errors='replace'):
    if l.startswith('[rsx-hb]'):
        t = int(re.search(r'ms=(\d+)', l).group(1)) / 1000.0
        continue
    r = w[int(t // W)]
    if l.startswith('[rsx-frame-perf]'):
        r['fr'] += 1
    elif l.startswith('[PT]') and 'fn=00536A30' in l:
        if ' ev=enter ' in l:
            r['ent'] += 1
        else:
            m = re.search(r'dur_us=(\d+)', l)
            r['dur'] += int(m.group(1)) / 1000.0 if m else 0
    elif l.startswith('[spurs-busy]'):
        m = re.search(r'runs=(\d+).*busy_ms=([\d.]+)', l)
        if m:
            r['runs'] += int(m.group(1))
            r['busy'] += float(m.group(2))
    elif l.startswith('[sc-wait]') and ' tid=1 ' in l:
        for name, ms in re.findall(r'(sc\d+)=([\d.]+)ms', l):
            r['sc'][name] += float(ms)
print('window_s frames page_enters page_ms spurs_runs spurs_busy_ms main_wait_ms')
for k in sorted(w):
    r = w[k]
    top = ' '.join(f'{a}={b:.0f}' for a, b in r['sc'].most_common(3))
    print(f"{int(k * W):4d} {r['fr']:5d} {r['ent']:4d} {r['dur']:8.0f} {r['runs']:7d} {r['busy']:9.1f}  {top}")
