#!/usr/bin/env python3
"""Hop-by-hop latency of main-thread JobBatch waits (Kksr36 joint PT + ftrace). Private.
usage: batch_hops.py pt.tsv cpath_waits.txt t0_s t1_s [site=413784]
For every JobBatch wait at <site> (4AACA0 caller lr) inside steady frames:
  start = the main thread's last SetCondition(false) (94CBD8 lr 4ABDD0, JobBatchInternal::Start) before the wait
  kick  = first SPURS lane pick with the 'kicked' flag (ftrace kind 24, a bit 16) after start
  j0/j1 = first job start / last job end (kind 26) between start and the SetCondition(true)
  sig   = SetCondition(true) on the wait's gate (JobBatchHandler, tid 12)
  exit  = wait exit"""
import sys, bisect, statistics as st, collections
OFF = -20263.5
pt, ft, T0, T1 = sys.argv[1], sys.argv[2], float(sys.argv[3]) * 1e6, float(sys.argv[4]) * 1e6
site = sys.argv[5] if len(sys.argv) > 5 else '413784'
ev = []
for l in open(pt):
    p = l.rstrip('\n').split('\t'); t = int(p[0])
    if T0 - 2e5 <= t <= T1 + 2e5: ev.append((t + OFF, int(p[1]), p[2], p[3], p[4], p[6], p[7]))
ev.sort()
jobs = []; kicks = []
for l in open(ft):
    if l[0] in '#TH': continue
    p = l.split()
    if len(p) != 6: continue
    k = int(p[0]); t0 = float(p[4])
    if t0 < T0 + OFF - 2e5 or t0 > T1 + OFF + 2e5: continue
    if k == 26 and p[2] != 'e0a08abe': jobs.append((t0, float(p[5]), p[2]))
    elif k == 24 and int(p[2], 16) >> 16 & 1: kicks.append(t0)
jobs.sort(); kicks.sort(); js = [j[0] for j in jobs]
frames = [e[0] for e in ev if e[1] == 1 and e[2] == 'enter' and e[3] == '5226A8']
sel = [(a, b) for a, b in zip(frames, frames[1:]) if T0 + OFF <= a and b <= T1 + OFF and b - a < 50e3]
def steady(t): return any(a <= t < b for a, b in sel)
starts = [e[0] for e in ev if e[1] == 1 and e[2] == 'enter' and e[3] == '94CBD8' and e[4] == '4ABDD0']
sig = collections.defaultdict(list)
for e in ev:
    if e[2] == 'enter' and e[3] == '94CBD8' and e[6] and int(e[6], 16) & 1: sig[e[5]].append(e[0])
stack = {}; iv = []
for e in ev:
    if e[1] != 1: continue
    if e[2] == 'enter': stack[e[3]] = e
    elif e[2] == 'exit' and e[3] in stack:
        s = stack.pop(e[3]); iv.append((s[0], e[0], e[3], s[4], s[5]))
cv = sorted(x for x in iv if x[2] == '94CC80'); cvs = [x[0] for x in cv]
H = collections.defaultdict(list)
for a, b, f, lr, r3 in iv:
    if f != '4AACA0' or lr != site or not steady(a): continue
    i = bisect.bisect_left(cvs, a)
    if i >= len(cv) or cv[i][0] > b: continue
    g = cv[i][4]; s = [q for q in sig.get(g, []) if cv[i][0] - 5 <= q <= b + 5]
    if not s: continue
    sg = s[-1]
    k = bisect.bisect_right(starts, a) - 1
    if k < 0: continue
    st0 = starts[k]
    kk = bisect.bisect_left(kicks, st0); kick = kicks[kk] if kk < len(kicks) else None
    inb = [j for j in jobs[bisect.bisect_left(js, st0):bisect.bisect_right(js, sg)] if j[1] <= sg]
    if not inb or kick is None: continue
    j0 = min(j[0] for j in inb); j1 = max(j[1] for j in inb)
    H['start->wait'].append(a - st0); H['start->kick'].append(kick - st0); H['kick->job0'].append(j0 - kick)
    H['exec j0->j1'].append(j1 - j0); H['j1->signal'].append(sg - j1); H['signal->exit'].append(b - sg)
    H['wait total'].append(b - a); H['start->exit'].append(b - st0); H['jobs'].append(len(inb))
    H['spu busy sum'].append(sum(j[1] - j[0] for j in inb))
print('site', site, 'batches', len(H['wait total']))
for k, v in H.items():
    v2 = sorted(v)
    print('  %-14s mean %7.1f  p10 %7.1f  p50 %7.1f  p90 %7.1f' % (k, st.mean(v), v2[len(v) // 10], v2[len(v) // 2], v2[len(v) * 9 // 10]))
