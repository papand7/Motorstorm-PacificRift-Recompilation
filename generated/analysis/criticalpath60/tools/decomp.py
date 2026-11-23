#!/usr/bin/env python3
"""Decompose every main-thread blocking interval of the Kksr36 race-intro frames (joint PT + ftrace).
Private, game-derived.  usage: decomp.py pt.tsv cpath_waits.txt t0_s t1_s
Clock: ftrace_us = PT_us - 20263.5 (fitted, see joint.py).
For JobBatch waits (4AACA0 lr=site, gate wait 94CC80):
  pre  = wait start -> first SPU job (kind 26) start inside the wait   (submission path latency)
  exec = first job start -> last job end before the SetCondition(true) on the gate
  hand = last job end -> SetCondition(true) by the JobBatchHandler (tid 12)
  wake = SetCondition(true) -> wait exit (main-thread usleep(250) spin quantum)
  If the gate was already signalled at wait start, the wait is 'nowork'.
For A4C590 (event-queue semaphore) waits: overlapping Havok tasks (kind 39) / jobs, and the last item ending before the exit.
For 50C818 (Present spin until the render-job counter is reached): last renderable job end vs spin exit."""
import sys, bisect, collections, statistics as st
OFF = -20263.5
pt, ft, T0, T1 = sys.argv[1], sys.argv[2], float(sys.argv[3]) * 1e6, float(sys.argv[4]) * 1e6
NAMES = {'2e29dde': 'vehphys', '2b93b080': 'renderable', '9cc94279': 'ProcEmit', '64ab83b': 'LibMP3',
         '1d51c6ce': 'HK2', '145c1b7b': 'HK1', '18345147': 'HKc', '1266e45a': 'HKd'}
nm = lambda k: NAMES.get(k, k)
ev = []
for l in open(pt):
    p = l.rstrip('\n').split('\t'); t = int(p[0])
    if T0 - 2e5 <= t <= T1 + 2e5: ev.append((t + OFF, int(p[1]), p[2], p[3], p[4], p[6], p[7]))
ev.sort()
jobs = []; hk = []
for l in open(ft):
    if l[0] in '#TH': continue
    p = l.split()
    if len(p) != 6: continue
    k = int(p[0]); t0 = float(p[4]); t1 = float(p[5])
    if t1 < T0 + OFF - 2e5 or t0 > T1 + OFF + 2e5: continue
    if k == 26 and p[2] != 'e0a08abe': jobs.append((t0, t1, p[2]))
    elif k == 39: hk.append((t0, t1, p[2]))
jobs.sort(); hk.sort()
js = [j[0] for j in jobs]
frames = [e[0] for e in ev if e[1] == 1 and e[2] == 'enter' and e[3] == '5226A8']
sel = [(a, b) for a, b in zip(frames, frames[1:]) if T0 + OFF <= a and b <= T1 + OFF and b - a < 50e3]
selset = sel
def frame_of(t):
    for a, b in selset:
        if a <= t < b: return (a, b)
    return None
sig = collections.defaultdict(list)
for e in ev:
    if e[2] == 'enter' and e[3] == '94CBD8' and e[6] and int(e[6], 16) & 1: sig[e[5]].append((e[0], e[1]))
stack = {}; iv = []
for e in ev:
    if e[1] != 1: continue
    if e[2] == 'enter': stack[e[3]] = e
    elif e[2] == 'exit' and e[3] in stack:
        s = stack.pop(e[3]); iv.append((s[0], e[0], e[3], s[4], s[5]))
iv.sort()
jbw = [x for x in iv if x[2] == '4AACA0']
cvw = [x for x in iv if x[2] == '94CC80']
cvs = [x[0] for x in cvw]
R = collections.defaultdict(lambda: collections.defaultdict(float)); N = collections.Counter()
lastimg = collections.defaultdict(collections.Counter)
nf = len(sel)
for a, b, f, lr, r3 in jbw:
    if not frame_of(a): continue
    i = bisect.bisect_left(cvs, a)
    if i >= len(cvw) or cvw[i][0] > b: continue
    c = cvw[i]; gate = c[4]; d = b - a
    key = lr
    N[key] += 1; R[key]['wait'] += d
    s = [q for q in sig.get(gate, []) if c[0] - 5 <= q[0] <= c[1] + 5]
    if d < 60 or not s:
        R[key]['nowork'] += d; continue
    sg = s[-1][0]
    inside = [j for j in jobs[bisect.bisect_left(js, a - 2000):bisect.bisect_right(js, sg)] if j[1] <= sg + 5 and j[1] >= a]
    started = [j for j in inside if j[0] >= a]
    if not inside:
        R[key]['hand_only'] += sg - a; R[key]['wake'] += b - sg; continue
    first = min(j[0] for j in started) if started else a
    last = max(inside, key=lambda j: j[1])
    lastimg[key][nm(last[2])] += 1
    R[key]['pre'] += max(first - a, 0)
    R[key]['exec'] += max(last[1] - max(first, a), 0)
    R[key]['hand'] += max(sg - last[1], 0)
    R[key]['wake'] += max(b - sg, 0)
    busy = sum(min(j[1], sg) - max(j[0], a) for j in inside)
    R[key]['spu_busy'] += busy
print('frames', nf, 'mean %.2f ms' % (sum(b - a for a, b in sel) / nf / 1e3))
print('JobBatch waits (ms/frame): site n/fr wait | nowork | pre(submit) exec hand(complete->signal) wake(signal->exit) | spu-busy-sum | last job')
tot = collections.Counter()
for k in sorted(R, key=lambda k: -R[k]['wait']):
    r = R[k]
    for x in r: tot[x] += r[x]
    print('  %-7s %5.1f %6.2f | %5.2f | %5.2f %5.2f %5.2f %5.2f | %5.2f | %s' % (k, N[k] / nf, r['wait'] / 1e3 / nf, r['nowork'] / 1e3 / nf, r['pre'] / 1e3 / nf,
          r['exec'] / 1e3 / nf, r['hand'] / 1e3 / nf, r['wake'] / 1e3 / nf, r['spu_busy'] / 1e3 / nf, dict(lastimg[k].most_common(3))))
print('  TOTAL         %6.2f | %5.2f | %5.2f %5.2f %5.2f %5.2f | %5.2f' % tuple(tot[x] / 1e3 / nf for x in ('wait', 'nowork', 'pre', 'exec', 'hand', 'wake', 'spu_busy')))
# A4C590 semaphore waits
S = collections.defaultdict(lambda: collections.defaultdict(float)); SN = collections.Counter(); slast = collections.defaultdict(collections.Counter)
hs = [h[0] for h in hk]
for a, b, f, lr, r3 in iv:
    if f != 'A4C590' or not frame_of(a): continue
    d = b - a; SN[lr] += 1; S[lr]['wait'] += d
    ov = [h for h in hk[max(0, bisect.bisect_left(hs, a - 20000)):bisect.bisect_right(hs, b)] if h[1] > a and h[0] < b]
    ovj = [j for j in jobs[bisect.bisect_left(js, a - 20000):bisect.bisect_right(js, b)] if j[1] > a and j[0] < b]
    if ov: S[lr]['hk_overlap'] += d
    elif ovj: S[lr]['job_overlap'] += d
    else: S[lr]['nothing'] += d
    ends = [x for x in ov + ovj if x[1] <= b + 5]
    if ends:
        l = max(ends, key=lambda x: x[1]); slast[lr][nm(l[2])] += 1; S[lr]['end_to_exit'] += b - l[1]
print('A4C590 waits (ms/frame): site n/fr wait | with HK task running | with only jobs | nothing on SPU | last-end->exit | last item')
for k in sorted(S, key=lambda k: -S[k]['wait']):
    r = S[k]
    print('  %-7s %5.1f %6.2f | %5.2f | %5.2f | %5.2f | %5.2f | %s' % (k, SN[k] / nf, r['wait'] / 1e3 / nf, r['hk_overlap'] / 1e3 / nf, r['job_overlap'] / 1e3 / nf,
          r['nothing'] / 1e3 / nf, r['end_to_exit'] / 1e3 / nf, dict(slast[k].most_common(3))))
# Present spin
sp = [x for x in iv if x[2] == '50C818' and frame_of(x[0])]
rj = [j for j in jobs if j[2] == '2b93b080']; rje = sorted(j[1] for j in rj)
lat = []; tot_sp = 0
for a, b, f, lr, r3 in sp:
    tot_sp += b - a
    i = bisect.bisect_right(rje, b + 5) - 1
    if i >= 0 and rje[i] >= a: lat.append(b - rje[i])
print('Present spin 50C818: %.2f ms/frame; spins ended by a renderable job end inside the spin: %d/%d, exit latency median %.0f us' % (
    tot_sp / 1e3 / nf, len(lat), len(sp), st.median(lat) if lat else -1))
# main-thread totals
blk = collections.Counter()
for a, b, f, lr, r3 in iv:
    if not frame_of(a): continue
    if f in ('4AACA0', 'A4C590', '50C818', '5226A8', '94CBD8', '50D868'): blk[f] += b - a
print('PT main-thread inclusive per frame (ms):', {k: round(v / 1e3 / nf, 2) for k, v in blk.items()})
# SPU busy per frame
for nmk, L in (('jobs', jobs), ('hk', hk)):
    c = collections.Counter()
    for t0, t1, k in L:
        if frame_of(t0): c[nm(k)] += t1 - t0
    print(nmk, 'SPU-busy ms/frame', {k: round(v / 1e3 / nf, 2) for k, v in c.most_common(10)})
