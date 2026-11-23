#!/usr/bin/env python3
"""Mean per-frame phase markers (Kksr36 steady race-intro frames, joint PT + ftrace). Private.
usage: phases.py pt.tsv cpath_waits.txt t0_s t1_s
Offsets in ms from the main thread's DisplayATG::Present (5226A8) entry that starts the frame."""
import sys, bisect, statistics as st, collections
OFF = -20263.5
pt, ft, T0, T1 = sys.argv[1], sys.argv[2], float(sys.argv[3]) * 1e6, float(sys.argv[4]) * 1e6
ev = []
for l in open(pt):
    p = l.rstrip('\n').split('\t'); t = int(p[0])
    if T0 - 2e5 <= t <= T1 + 2e5: ev.append((t + OFF, int(p[1]), p[2], p[3], p[4], p[6], p[7]))
ev.sort()
fr = []
for l in open(ft):
    if l[0] in '#TH': continue
    p = l.split()
    if len(p) != 6: continue
    k = int(p[0]); t0 = float(p[4])
    if t0 < T0 + OFF - 2e5 or t0 > T1 + OFF + 2e5: continue
    if k in (26, 38, 39): fr.append((t0, float(p[5]), k, p[2], p[1]))
fr.sort()
frames = [e[0] for e in ev if e[1] == 1 and e[2] == 'enter' and e[3] == '5226A8']
sel = [(a, b) for a, b in zip(frames, frames[1:]) if T0 + OFF <= a and b <= T1 + OFF and b - a < 50e3]
stack = {}; iv = []
for e in ev:
    if e[1] != 1: continue
    if e[2] == 'enter': stack[e[3]] = e
    elif e[2] == 'exit' and e[3] in stack:
        s = stack.pop(e[3]); iv.append((s[0], e[0], e[3], s[4]))
iv.sort()
M = collections.defaultdict(list)
def add(k, v): M[k].append(v / 1e3)
for a, b in sel:
    I = [x for x in iv if a <= x[0] < b]; F = [x for x in fr if a <= x[0] < b]
    add('frame', b - a)
    pe = [x for x in I if x[2] == '5226A8']
    if pe: add('present+spin end', pe[0][1] - a)
    hs = [x for x in F if x[2] == 38 and x[4] == '17364']
    if hs: add('first HK submit (main)', hs[0][0] - a)
    he = [x for x in F if x[2] == 39]
    if he: add('last HK task end', max(x[1] for x in he) - a); add('HK task SPU-ms', sum(x[1] - x[0] for x in he))
    vp = [x for x in I if x[2] == '4AACA0' and x[3] == '413784']
    if vp: add('vehphys wait1 start', vp[0][0] - a); add('vehphys wait2 end', vp[-1][1] - a)
    pv = [x for x in F if x[2] == 26 and x[3] == '602e92cb']
    if pv: add('first 602e92cb job', pv[0][0] - a); add('last 602e92cb end', max(x[1] for x in pv) - a); add('602e92cb SPU-ms', sum(x[1] - x[0] for x in pv)); add('602e92cb n', len(pv) * 1e3)
    vw = [x for x in I if x[2] == '4AACA0' and x[3] == '5F7588']
    if vw: add('first Vis wait', vw[0][0] - a); add('last Vis wait end', vw[-1][1] - a)
    ep = [x for x in I if x[2] == '50D868']
    if ep: add('first ExecutePushBuffer', ep[0][0] - a); add('last ExecutePushBuffer', ep[-1][1] - a); add('EPB n', len(ep) * 1e3)
    rj = [x for x in F if x[2] == 26 and x[3] == '2b93b080']
    if rj: add('first renderable job', rj[0][0] - a); add('last renderable end', max(x[1] for x in rj) - a); add('renderable SPU-ms', sum(x[1] - x[0] for x in rj)); add('renderable n', len(rj) * 1e3)
    d4 = [x for x in I if x[2] == '4AACA0' and x[3] == '49DCF8']
    if d4: add('49DCF8 wait start', d4[0][0] - a); add('49DCF8 wait end', d4[0][1] - a)
# next frame's spin = this frame's renderable completion
print('frames', len(sel))
for k, v in M.items():
    v2 = sorted(v)
    print('  %-26s mean %7.2f  p50 %7.2f  p10 %7.2f  p90 %7.2f' % (k, st.mean(v), v2[len(v) // 2], v2[len(v) // 10], v2[len(v) * 9 // 10]))
