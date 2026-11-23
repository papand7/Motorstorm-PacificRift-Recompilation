#!/usr/bin/env python3
"""Joint PT + ftrace timeline of main-thread frames (Kksr36).  Private (game-derived).
Clock: ftrace_us = PT_us + OFF (OFF = -20263.5, fitted on 353 matched cv-wait ends, p10-p90 2.4 us).
usage: joint.py pt.tsv cpath_waits.txt t0_s t1_s [dump_frames]
Prints per frame: main intervals (PT), SPU jobs/tasks overlapping, and the last SPU item ending before each wake."""
import sys, bisect, collections
OFF = -20263.5
pt, ft, T0, T1 = sys.argv[1], sys.argv[2], float(sys.argv[3]) * 1e6, float(sys.argv[4]) * 1e6
dump = int(sys.argv[5]) if len(sys.argv) > 5 else 2
NAMES = {'2e29dde': 'vehphys', '2b93b080': 'renderable', '9cc94279': 'ProcEmit', '64ab83b': 'LibMP3',
         '1d51c6ce': 'HK2', '145c1b7b': 'HK1', '18345147': 'HKc', '1266e45a': 'HKd'}
nm = lambda k: NAMES.get(k, k)
ev = []
for l in open(pt):
    p = l.rstrip('\n').split('\t'); t = int(p[0])
    if T0 - 1e5 <= t <= T1 + 1e5: ev.append((t + OFF, int(p[1]), p[2], p[3], p[4], p[6], p[7]))
ev.sort()
work = []  # (t0,t1,kind,id,who)
subm = []
h12 = []
for l in open(ft):
    if l[0] in '#TH': continue
    p = l.split()
    if len(p) != 6: continue
    k = int(p[0]); t0 = float(p[4]); t1 = float(p[5])
    if t1 < T0 + OFF - 1e5 or t0 > T1 + OFF + 1e5: continue
    if k == 26 and p[2] != 'e0a08abe': work.append((t0, t1, 'job', p[2], int(p[1])))
    elif k == 39: work.append((t0, t1, 'hk', p[2], int(p[1])))
    elif k == 38: subm.append((t0, p[2], int(p[1])))
    elif k == 2 and p[1] == '12': h12.append((t0, t1))
work.sort()
frames = [e[0] for e in ev if e[1] == 1 and e[2] == 'enter' and e[3] == '5226A8']
stack = {}; iv = []
for e in ev:
    if e[1] != 1: continue
    if e[2] == 'enter': stack[e[3]] = e
    elif e[2] == 'exit' and e[3] in stack:
        s = stack.pop(e[3]); iv.append((s[0], e[0], e[3], s[4], s[5]))
sig = [(e[0], e[1], e[5]) for e in ev if e[2] == 'enter' and e[3] in ('94CBD8',) and e[6] and int(e[6], 16) & 1]
post = [(e[0], e[1], e[5], e[4]) for e in ev if e[2] == 'enter' and e[3] == 'A4C7B8']
def frame_dump(a, b):
    print('=== frame +0 = %.3f s (ftrace clock), %.2f ms' % (a / 1e6, (b - a) / 1e3))
    rows = []
    for x in iv:
        if a <= x[0] < b and (x[1] - x[0] >= 50 or x[2] in ('50C818',)) and x[2] in ('4AACA0', 'A4C590', '50C818', '5226A8', '50D868'):
            rows.append((x[0], 'MAIN %-7s lr=%-6s %6.2f ms obj=%s' % (x[2], x[3], (x[1] - x[0]) / 1e3, x[4]), x))
    for w in work:
        if a <= w[0] < b: rows.append((w[0], '      spu%-2d %-4s %-11s %6.3f ms (ends +%.2f)' % (w[4] % 100, w[2], nm(w[3]), (w[1] - w[0]) / 1e3, (w[1] - a) / 1e3), None))
    for s in subm:
        if a <= s[0] < b: rows.append((s[0], '      submit %s by host %d' % (nm(s[1]), s[2]), None))
    for s in h12:
        if a <= s[1] < b: rows.append((s[1], '      H12 wake (slept %.0f us)' % (s[1] - s[0]), None))
    for s in sig:
        if a <= s[0] < b and s[1] != 1: rows.append((s[0], '      SetCond(true) tid %d gate %s' % (s[1], s[2]), None))
    for s in post:
        if a <= s[0] < b: rows.append((s[0], '      SemaPost tid %d obj %s lr %s' % (s[1], s[2], s[3]), None))
    rows.sort(key=lambda r: r[0])
    for r in rows: print('  +%7.3f %s' % ((r[0] - a) / 1e3, r[1]))
sel = [(a, b) for a, b in zip(frames, frames[1:]) if T0 + OFF <= a and b <= T1 + OFF and b - a < 50e3]
print('frames', len(sel))
for a, b in sel[:dump]: frame_dump(a, b)
