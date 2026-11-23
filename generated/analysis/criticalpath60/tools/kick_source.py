#!/usr/bin/env python3
"""Who kicks SPURS Wws job workloads? Phase test between kicked lane picks (ftrace kind 24, kicked bit),
main-thread JobBatchInternal::Start (PT 94CBD8 lr 4ABDD0, value 0) and JobBatchHandler SetCondition(true) (tid 12).
usage: kick_source.py pt.tsv cpath_waits.txt t0_s t1_s   (private)"""
import sys, bisect, collections
OFF = -20263.5
pt, ft, T0, T1 = sys.argv[1], sys.argv[2], float(sys.argv[3]) * 1e6, float(sys.argv[4]) * 1e6
starts = []; sigs = []
for l in open(pt):
    p = l.rstrip('\n').split('\t'); t = int(p[0])
    if not (T0 <= t <= T1) or p[2] != 'enter' or p[3] != '94CBD8': continue
    if p[1] == '1' and p[4] == '4ABDD0': starts.append(t + OFF)
    if p[1] == '12' and p[7] and int(p[7], 16) & 1: sigs.append(t + OFF)
kicks = []
for l in open(ft):
    p = l.split()
    if len(p) == 6 and p[0] == '24' and int(p[2], 16) >> 16 & 1:
        t = float(p[4])
        if T0 + OFF <= t <= T1 + OFF: kicks.append(t)
kicks.sort(); starts.sort(); sigs.sort()
# cluster kicks (all lanes picked within 30 us = one kick)
kc = []
for k in kicks:
    if not kc or k - kc[-1] > 30: kc.append(k)
print('kick clusters', len(kc), 'starts', len(starts), 'handler signals', len(sigs))
def hist(vals, edges):
    h = collections.Counter()
    for v in vals:
        for e in edges:
            if v < e: h[e] += 1; break
        else: h['inf'] += 1
    return [(e, h[e]) for e in edges + ['inf']]
E = [10, 25, 50, 100, 200, 300, 400, 500, 600, 800, 1000, 2000]
d1 = []
for k in kc:
    i = bisect.bisect_right(starts, k) - 1
    if i >= 0: d1.append(k - starts[i])
print('kick - previous main Start (us):', hist(d1, E))
d2 = []
for k in kc:
    i = bisect.bisect_left(sigs, k)
    if i < len(sigs): d2.append(sigs[i] - k)
print('next handler SetCond(true) - kick (us):', hist(d2, E))
d3 = []
for s in sigs:
    i = bisect.bisect_right(kc, s) - 1
    if i >= 0: d3.append(s - kc[i])
print('handler SetCond(true) - previous kick (us):', hist(d3, E))
# handler signal clusters spacing
sc = []
for s in sigs:
    if not sc or s - sc[-1] > 60: sc.append(s)
gaps = [b - a for a, b in zip(sc, sc[1:])]
print('handler signal-cluster spacing (us):', hist(gaps, [300, 450, 500, 550, 600, 700, 1000, 1100, 1200, 1700, 2500]))
