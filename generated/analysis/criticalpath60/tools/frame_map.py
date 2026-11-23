#!/usr/bin/env python3
"""Per-frame main-thread map from a compacted PT trace (pt_compact.py output).
usage: frame_map.py pt.tsv t0_s t1_s [show_frames=3]
Frame = main-thread (tid 1) DisplayATG::Present 5226A8 enter to the next.
Per frame: 4AACA0 JobBatch::Wait (by caller lr), 94CC80 cv waits (by gate + the 4AACA0 caller),
A4C590 semaphore waits (by lr), 50C818 spin, 5226A8 Present. For each 94CC80 wait: the last
94CBD8 SetCondition(true) on that gate before the wake (signal tid, latency); for each A4C590 wait:
the A4C7B8 post on the object (poster tid, latency).  Labels: all values are PT-hook times (lean
hooks; each hook adds a little overhead)."""
import sys, bisect, collections, statistics as st
path, T0, T1 = sys.argv[1], float(sys.argv[2]) * 1e6, float(sys.argv[3]) * 1e6
show = int(sys.argv[4]) if len(sys.argv) > 4 else 3
ev = []
for l in open(path):
    p = l.rstrip('\n').split('\t')
    t = int(p[0])
    if t < T0 - 2e6 or t > T1 + 2e6: continue
    ev.append((t, int(p[1]), p[2], p[3], p[4], p[5], p[6], p[7], p[8]))
ev.sort(key=lambda e: e[0])
# signals
sig = collections.defaultdict(list)   # gate -> [(t, tid)]  SetCondition(true)
post = collections.defaultdict(list)  # sema -> [(t, tid, lr)]
for e in ev:
    if e[2] == 'enter' and e[3] == '94CBD8' and e[7] and int(e[7], 16) & 1:
        sig[e[6]].append((e[0], e[1], e[4]))
    if e[2] == 'enter' and e[3] == 'A4C7B8':
        post[e[6]].append((e[0], e[1], e[4]))
frames = [e[0] for e in ev if e[1] == 1 and e[2] == 'enter' and e[3] == '5226A8' and T0 <= e[0] <= T1]
print('frames', len(frames) - 1, 'mean %.2f ms' % ((frames[-1] - frames[0]) / 1e3 / (len(frames) - 1)))
ft = [(b - a) / 1e3 for a, b in zip(frames, frames[1:])]
ft.sort(); print('frame ms p10 %.1f p50 %.1f p90 %.1f' % (ft[len(ft) // 10], ft[len(ft) // 2], ft[int(len(ft) * .9)]))
# main-thread intervals
stack = {}
ivs = []   # (t0, t1, fn, lr, r3, extra)
for e in ev:
    if e[1] != 1: continue
    if e[2] == 'enter': stack[e[3]] = e
    elif e[2] == 'exit' and e[3] in stack:
        en = stack.pop(e[3]); ivs.append((en[0], e[0], e[3], en[4], en[6], en[8]))
ivs.sort()
def in_frames(t):
    i = bisect.bisect_right(frames, t) - 1
    return i if 0 <= i < len(frames) - 1 else None
agg = collections.Counter(); cnt = collections.Counter()
wake = collections.defaultdict(list)
# 4AACA0 caller per cv wait: the enclosing 4AACA0 interval
jb = [(a, b, lr, r3) for a, b, f, lr, r3, x in ivs if f == '4AACA0']
jbs = [x[0] for x in jb]
detail = collections.defaultdict(list)
for a, b, f, lr, r3, x in ivs:
    i = in_frames(a)
    if i is None: continue
    d = (b - a)
    if f == '94CC80':
        k = jb[bisect.bisect_right(jbs, a) - 1] if jbs and bisect.bisect_right(jbs, a) else None
        caller = k[2] if k and k[0] <= a <= k[1] else '?'
        key = ('cvwait', caller)
        s = sig.get(r3, [])
        j = bisect.bisect_right([q[0] for q in s], b) - 1 if s else -1
        if j >= 0 and s[j][0] >= a - 50:
            wake['cv lat'].append(b - s[j][0]); wake['cv sigtid %d' % s[j][1]].append(d)
        elif j >= 0: wake['cv signalled-before-wait'].append(d)
        detail[i].append((a - frames[i], d, 'cv', caller, r3, (s[j][1], b - s[j][0]) if j >= 0 and s[j][0] >= a - 50 else None))
    elif f == 'A4C590':
        key = ('sema', lr)
        s = post.get(r3, [])
        j = bisect.bisect_right([q[0] for q in s], b) - 1 if s else -1
        if d >= 60:
            if j >= 0 and s[j][0] >= a - 50:
                wake['sema lat'].append(b - s[j][0]); wake['sema posttid %d lr %s' % (s[j][1], s[j][2])].append(d)
            detail[i].append((a - frames[i], d, 'sema', lr, r3, (s[j][1], b - s[j][0]) if j >= 0 and s[j][0] >= a - 50 else None))
    else:
        key = (f, lr)
        if f in ('50C818',) or d >= 200: detail[i].append((a - frames[i], d, f, lr, r3, None))
    agg[key] += d; cnt[key] += 1
n = len(frames) - 1
print('per frame (ms/frame, count/frame):')
for k, v in sorted(agg.items(), key=lambda x: -x[1]):
    if v / 1e3 / n >= 0.02: print('  %-30s %6.2f ms  n %6.1f' % (k, v / 1e3 / n, cnt[k] / n))
print('wake paths:')
for k, v in sorted(wake.items()):
    if 'lat' in k: print('  %-34s n/fr %5.1f  mean %6.0f us p50 %6.0f p90 %6.0f' % (k, len(v) / n, st.mean(v), sorted(v)[len(v) // 2], sorted(v)[int(len(v) * .9)]))
    else: print('  %-34s n/fr %5.1f  wait ms/fr %6.2f' % (k, len(v) / n, sum(v) / 1e3 / n))
step = max(1, n // max(show, 1))
for i in list(range(0, n, step))[:show]:
    print('--- frame %d (%.1f ms)' % (i, (frames[i + 1] - frames[i]) / 1e3))
    for off, d, kind, lr, r3, w in sorted(detail[i]):
        if d < 60 and kind != '50C818': continue
        print('   +%7.2f ms  %7.2f ms  %-7s lr=%-7s obj=%s %s' % (off / 1e3, d / 1e3, kind, lr, r3, ('woken by tid %d after %d us' % w) if w else ''))
