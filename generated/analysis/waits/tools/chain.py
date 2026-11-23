#!/usr/bin/env python3
"""Dependency chain of the race main thread from a [PT] log made with waits_sites.cfg.
usage: chain.py stderr.log [main_tid=1] [frames=6]
Per frame (5226A8 enter to next): each 94CC80 Wait (dur, gate, caller lr), the SetCondition(true) on the same gate
(tid, time) and the wake latency (Wait exit - that signal), Start (SetCondition false) to signal time (batch latency),
A4C590 semaphore waits vs the A4C7B8 post on the same obj, and the 50C818 spin."""
import re, sys, collections
log = sys.argv[1]; main = int(sys.argv[2]) if len(sys.argv) > 2 else 1
nfr = int(sys.argv[3]) if len(sys.argv) > 3 else 6
ev = []
for l in open(log, encoding='latin-1'):
    if not l.startswith('[PT] t='): continue
    m = re.match(r'\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=(\w+) lr=(\w+)(.*)', l)
    if not m: continue
    kv = dict(re.findall(r'(\S+?)=(\S+)', m.group(6)))
    ev.append((int(m.group(1)), int(m.group(2)), m.group(3), kv.get('fn', m.group(4)).upper(), m.group(5), kv))
def fn(e): return e[3].lstrip('0')
frames = [e[0] for e in ev if e[1] == main and e[2] == 'enter' and fn(e) == '5226A8']
print('frames seen', len(frames))
sig = collections.defaultdict(list)    # gate -> [(t, tid, val, lr)]
post = collections.defaultdict(list)   # sema obj -> [(t, tid, lr)]
for e in ev:
    if e[2] == 'enter' and fn(e) == '94CBD8':
        sig[e[5].get('r3')].append((e[0], e[1], e[5].get('r4'), e[4]))
    if e[2] == 'enter' and fn(e) == 'A4C7B8':
        post[e[5].get('r3')].append((e[0], e[1], e[4]))
def after(lst, t, pred=lambda x: True):
    c = [x for x in lst if x[0] >= t and pred(x)]
    return c[0] if c else None
stat = collections.defaultdict(list)
enters = {}
for i, e in enumerate(ev):
    if e[1] != main: continue
    f = fn(e)
    if e[2] == 'enter': enters[f] = e
    if e[2] != 'exit' or f not in ('94CC80', 'A4C590', '50C818'): continue
    en = enters.get(f)
    if not en: continue
    d = int(e[5].get('dur_us', 0)); t0 = en[0]; t1 = e[0]
    if f == '94CC80':
        g = en[5].get('r3')
        s = after(sig[g], t0 - 1, lambda x: x[2] and int(x[2], 16) & 1) if g in sig else None
        stat['cv_wait'].append(d)
        if s and s[0] <= t1: stat['cv_wake_latency'].append(t1 - s[0]); stat['cv_signal_tid_%d' % s[1]].append(d)
    elif f == 'A4C590':
        o = en[5].get('r3'); p = after(post[o], t0 - 1) if o in post else None
        stat['sema_wait'].append(d)
        if p and p[0] <= t1: stat['sema_wake_latency'].append(t1 - p[0]); stat['sema_post_tid_%d' % p[1]].append(d)
    else: stat['spin_50C818'].append(d)
n = max(len(frames) - 1, 1)
print('per frame (all main-thread episodes):')
for k, v in sorted(stat.items()):
    v.sort()
    print(f'  {k:24s} n/frame {len(v)/n:6.1f}  ms/frame {sum(v)/1e3/n:6.2f}  avg {sum(v)/len(v):7.0f} us  p50 {v[len(v)//2]} p90 {v[int(len(v)*.9)]}')
for a, b in list(zip(frames, frames[1:]))[-nfr:]:
    print(f'--- frame {a}..{b} ({(b-a)/1e3:.1f} ms)')
    for e in ev:
        if a <= e[0] < b and (e[1] == main and e[2] == 'exit' and fn(e) in ('94CC80', 'A4C590', '50C818')
                              or e[2] == 'enter' and fn(e) in ('94CBD8', 'A4C7B8', '50D868') or e[2] == 'mem'):
            print(f'  +{(e[0]-a)/1e3:7.3f} ms tid {e[1]:2d} {e[2]:5s} {fn(e)} {e[5].get("dur_us","")} r3={e[5].get("r3","")} r4={e[5].get("r4","")} lr={e[4]}')
