#!/usr/bin/env python3
"""SPU concurrency by frame phase (Kksr36 steady race-intro frames; joint PT + ftrace). Private.
usage: lanes.py pt.tsv cpath_waits.txt t0_s t1_s
Phases per frame (main thread, PT): P0 present/spin; SIM = spin end -> first ExecutePushBuffer (50D868);
EMIT = first -> last ExecutePushBuffer exit; TAIL = last EPB exit -> next frame's Present entry; SPIN = 50C818.
For each phase: wall ms, mean concurrent Wws jobs (kind 26, any lane), mean concurrent Havok tasks (kind 39),
share of time with >= 5 Wws jobs running (5 SPURS lanes = saturated), and main-thread wait share."""
import sys, bisect, collections, statistics as st
OFF = -20263.5
pt, ft, T0, T1 = sys.argv[1], sys.argv[2], float(sys.argv[3]) * 1e6, float(sys.argv[4]) * 1e6
ev = []
for l in open(pt):
    p = l.rstrip('\n').split('\t'); t = int(p[0])
    if T0 - 2e5 <= t <= T1 + 2e5 and p[1] == '1': ev.append((t + OFF, p[2], p[3], p[4]))
ev.sort()
J = []; H = []
for l in open(ft):
    if l[0] in '#TH': continue
    p = l.split()
    if len(p) != 6: continue
    k = int(p[0]); a = float(p[4]); b = float(p[5])
    if b < T0 + OFF - 2e5 or a > T1 + OFF + 2e5: continue
    if k == 26 and p[2] != 'e0a08abe': J.append((a, b, p[2]))
    elif k == 39: H.append((a, b, p[2]))
def step(items):
    e = sorted([(a, 1) for a, b, _ in items] + [(b, -1) for a, b, _ in items])
    ts = []; cs = []; c = 0
    for t, d in e:
        c += d; ts.append(t); cs.append(c)
    return ts, cs
jt, jc = step(J); ht, hc = step(H)
def integ(ts, cs, a, b, thr=None):
    """time-weighted mean of the step function over [a,b] (or share of time >= thr)"""
    i = bisect.bisect_right(ts, a) - 1; cur = a; acc = 0.0
    while cur < b:
        nxt = ts[i + 1] if i + 1 < len(ts) else b
        nxt = min(max(nxt, cur), b)
        v = cs[i] if i >= 0 else 0
        acc += (nxt - cur) * ((v >= thr) if thr else v)
        cur = nxt; i += 1
        if nxt == b: break
    return acc / (b - a) if b > a else 0
frames = [e[0] for e in ev if e[1] == 'enter' and e[2] == '5226A8']
sel = [(a, b) for a, b in zip(frames, frames[1:]) if T0 + OFF <= a and b <= T1 + OFF and b - a < 50e3]
stack = {}; iv = []
for e in ev:
    if e[1] == 'enter': stack[e[2]] = e
    elif e[1] == 'exit' and e[2] in stack:
        s = stack.pop(e[2]); iv.append((s[0], e[0], e[2], s[3]))
iv.sort()
waits = [(a, b) for a, b, f, lr in iv if f in ('4AACA0', 'A4C590', '50C818')]
ws = [w[0] for w in waits]
def wait_share(a, b):
    tot = 0
    for w0, w1 in waits[max(0, bisect.bisect_left(ws, a) - 2):bisect.bisect_right(ws, b)]:
        tot += max(0, min(w1, b) - max(w0, a))
    return tot / (b - a) if b > a else 0
R = collections.defaultdict(lambda: collections.defaultdict(list))
for a, b in sel:
    I = [x for x in iv if a <= x[0] < b]
    pe = [x for x in I if x[2] == '5226A8']; ep = [x for x in I if x[2] == '50D868']
    if not pe or not ep: continue
    p0e = pe[0][1]; e0 = ep[0][0]; e1 = ep[-1][1]
    for name, x0, x1 in (('P0 present+spin', a, p0e), ('SIM (to first EPB)', p0e, e0), ('EMIT (EPB span)', e0, e1), ('TAIL (to next Present)', e1, b)):
        if x1 <= x0: continue
        r = R[name]
        r['ms'].append((x1 - x0) / 1e3); r['jobs'].append(integ(jt, jc, x0, x1)); r['hk'].append(integ(ht, hc, x0, x1))
        r['sat5'].append(integ(jt, jc, x0, x1, 5)); r['wait'].append(wait_share(x0, x1))
print('frames', len(sel))
print('%-24s %7s %9s %9s %10s %10s' % ('phase', 'ms', 'Wws jobs', 'HK tasks', '>=5 jobs', 'main wait'))
for k in ('P0 present+spin', 'SIM (to first EPB)', 'EMIT (EPB span)', 'TAIL (to next Present)'):
    r = R[k]
    print('%-24s %7.2f %9.2f %9.2f %9.0f%% %9.0f%%' % (k, st.mean(r['ms']), st.mean(r['jobs']), st.mean(r['hk']), 100 * st.mean(r['sat5']), 100 * st.mean(r['wait'])))
