"""T161 V5: bound the PS3_LWCOND_WAKE fallbacks of a wake-on run per (thread, lwcond) from the
PS3_LWCOND_TRACE lines (the V4 build has no per-fallback record).
In wake mode every wait call returns either because a signal woke it or as a poll_ms fallback.
Open episodes ([lwc-open], cumulative polls/sig/open_ms) give, per 1 s window and key:
  lower  max(0, d_polls - d_sig)        (each signal on the lwcond wakes this waiter at most once)
  exact  d_polls                        when d_sig == 0 (no signal at all: every return is a fallback)
  upper  min(d_polls, d_open_ms // poll_ms + 1)
Closed detailed episodes ([lwc-ep], selected threads) add max(0, polls - sig). The [lwc-wake]
window totals are the ground truth the bounds are checked against.
  py -3 fb_attr_t161.py <run dir> [poll_ms=100] [--json out]"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

run = Path(sys.argv[1])
poll_ms = 100.0
out = None
for a in sys.argv[2:]:
    if a.startswith('poll_ms='):
        poll_ms = float(a[8:])
out = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
kv = re.compile(r'(\w+)=(\S+)')
prev = {}
lo, ex, up, polls, sigs, wins_fb = (defaultdict(float) for _ in range(6))
ep_lo = defaultdict(int)
ep_n = defaultdict(int)
truth = []
for line in open(run / 'stderr.log', encoding='utf-8', errors='replace'):
    if line.startswith('[lwc-open]'):
        d = dict(kv.findall(line))
        k = (int(d['tid']), d['cv'])
        cur = (float(d['open_ms']), int(d['polls']), int(d['sig']))
        p = prev.get(k)
        if p is None or cur[1] < p[1] or cur[0] < p[0]:
            p = (0.0, 0, 0)                    # a new episode began in this window
        dt, dp, ds = cur[0] - p[0], cur[1] - p[1], cur[2] - p[2]
        prev[k] = cur
        polls[k] += dp
        sigs[k] += ds
        lo[k] += max(0, dp - ds)
        if ds == 0:
            ex[k] += dp
        u = min(dp, int(dt // poll_ms) + 1) if dp else 0
        up[k] += u
        wins_fb[k] += u > 0
    elif line.startswith('[lwc-ep]'):
        d = dict(kv.findall(line))
        k = (int(d['tid']), d['cv'])
        ep_n[k] += 1
        ep_lo[k] += max(0, int(d['polls']) - int(d['sig']))
    elif line.startswith('[lwc-wake] window_ms='):
        truth.append(int(dict(kv.findall(line))['fallback']))
total = sum(truth)
keys = sorted(set(lo) | set(ep_lo), key=lambda k: (k[0], k[1]))
rows = []
for k in keys:
    rows.append(dict(tid=k[0], cv=k[1], open_polls=int(polls[k]), open_sig=int(sigs[k]), lower=int(lo[k] + ep_lo[k]),
                     exact_nosig=int(ex[k]), upper_open=int(up[k]), ep_closed=ep_n[k], ep_lower=ep_lo[k]))
L = sum(r['lower'] for r in rows)
res = dict(run=str(run), poll_ms=poll_ms, fallback_total=total, windows=len(truth), lower_sum=L,
           exact_nosig_sum=sum(r['exact_nosig'] for r in rows), rows=rows)
print(f"fallback total {total} over {len(truth)} windows; attributed lower bound {L} ({100.0 * L / max(total, 1):.1f} %)")
print(f"{'tid':>4} {'cv':>11} {'polls':>8} {'sig':>8} {'lower':>6} {'nosig':>6} {'upper':>6} {'ep_lo':>6}")
for r in rows:
    if r['lower'] or r['upper_open']:
        print(f"{r['tid']:>4} {r['cv']:>11} {r['open_polls']:>8} {r['open_sig']:>8} {r['lower']:>6} {r['exact_nosig']:>6} {r['upper_open']:>6} {r['ep_lower']:>6}")
if out:
    Path(out).write_text(json.dumps(res, indent=1), encoding='utf-8')
