#!/usr/bin/env python3
"""MODELLED: effect of removing the interpreter share of renderablejob (2b93b080) on the frame tail.
Private (game-derived). usage: rj_model.py pt.tsv cpath_waits.txt t0_s t1_s [ns_per_step_new=1.5] [lanes=5]
Per steady frame (Kksr36 race intro, joint PT + ftrace):
  * all Wws jobs (kind 26) released at their observed start, durations observed;
  * renderable jobs re-timed: d' = d - steps * (11.1 - new) ns  (fit: d = 314 us + 11.1 ns * steps, R^2 0.82);
  * greedy list scheduling on `lanes` lanes in release order (jobs never start before their observed start);
  * report: observed vs modelled 'tail' = last renderable end - last ExecutePushBuffer exit (what the
    Present spin waits for once the main thread is done), and SPU-ms removed.
Validation: the same scheduler with unchanged durations ('base') against the observed tail."""
import sys, heapq, bisect, statistics as st
OFF = -20263.5; FIT_NS = 11.1
pt, ft, T0, T1 = sys.argv[1], sys.argv[2], float(sys.argv[3]) * 1e6, float(sys.argv[4]) * 1e6
NEW = float(sys.argv[5]) if len(sys.argv) > 5 else 1.5
L = int(sys.argv[6]) if len(sys.argv) > 6 else 5
REL = sys.argv[7] if len(sys.argv) > 7 else 'start'   # 'start' = observed start; 'epb' = latest ExecutePushBuffer entry before it (renderable only)
ev = []
for l in open(pt):
    p = l.rstrip('\n').split('\t'); t = int(p[0])
    if T0 - 2e5 <= t <= T1 + 2e5 and p[1] == '1' and p[3] in ('5226A8', '50D868'): ev.append((t + OFF, p[2], p[3]))
ev.sort()
jobs = []; steps = {}
for l in open(ft):
    p = l.split()
    if len(p) != 6: continue
    if p[0] == '26' and p[2] != 'e0a08abe':
        a = float(p[4]); b = float(p[5])
        if T0 + OFF - 2e5 <= a <= T1 + OFF + 2e5: jobs.append([a, b, p[2], 0])
    elif p[0] == '27' and p[3] == '2b93b080':
        steps.setdefault(round(float(p[4]), 1), []).append(int(p[2], 16))
for j in jobs:
    if j[2] == '2b93b080':
        k = round(j[1], 1)
        for kk in (k, round(k - .1, 1), round(k + .1, 1)):
            if steps.get(kk): j[3] = steps[kk].pop(); break
jobs.sort()
frames = [e[0] for e in ev if e[1] == 'enter' and e[2] == '5226A8']
sel = [(a, b) for a, b in zip(frames, frames[1:]) if T0 + OFF <= a and b <= T1 + OFF and b - a < 50e3]
epbx = sorted(e[0] for e in ev if e[1] == 'exit' and e[2] == '50D868')
epbn = sorted(e[0] for e in ev if e[1] == 'enter' and e[2] == '50D868')
def rel(j):
    if REL != 'epb' or j[2] != '2b93b080': return j[0]
    i = bisect.bisect_right(epbn, j[0]) - 1
    return epbn[i] if i >= 0 and j[0] - epbn[i] < 20000 else j[0]
def sched(items, lanes):
    free = [0.0] * lanes; heapq.heapify(free); out = []
    for rel, dur, kind in items:
        t = heapq.heappop(free); s = max(t, rel); e = s + dur
        heapq.heappush(free, e); out.append((s, e, kind))
    return out
obs = []; base = []; new = []; rm = []
for a, b in sel:
    x = [e for e in epbx if a <= e < b]
    if not x: continue
    lastepb = x[-1]
    fj = [j for j in jobs if a - 3000 <= j[0] < b]
    rj = [j for j in fj if j[2] == '2b93b080']
    if not rj: continue
    items_b = sorted((rel(j), j[1] - j[0], j[2]) for j in fj)
    items_n = sorted((rel(j), max(j[1] - j[0] - (j[3] * (FIT_NS - NEW) / 1e3 if j[2] == '2b93b080' else 0), 5.0), j[2]) for j in fj)
    sb = sched(items_b, L); sn = sched(items_n, L)
    lb = max(e for s, e, k in sb if k == '2b93b080'); ln = max(e for s, e, k in sn if k == '2b93b080')
    lo = max(j[1] for j in rj)
    obs.append(lo - lastepb); base.append(lb - lastepb); new.append(ln - lastepb)
    rm.append(sum(i[1] for i in items_b) - sum(i[1] for i in items_n))
print('frames', len(obs), 'lanes', L, 'new ns/step', NEW, 'release', REL)
print('tail (last renderable end - last EPB exit), ms: observed mean %.2f p50 %.2f | model-base mean %.2f p50 %.2f | model-new mean %.2f p50 %.2f'
      % (st.mean(obs) / 1e3, st.median(obs) / 1e3, st.mean(base) / 1e3, st.median(base) / 1e3, st.mean(new) / 1e3, st.median(new) / 1e3))
print('modelled tail reduction: mean %.2f ms, p50 %.2f ms; SPU-ms removed per frame: mean %.2f' %
      ((st.mean(base) - st.mean(new)) / 1e3, (st.median(base) - st.median(new)) / 1e3, st.mean(rm) / 1e3))
