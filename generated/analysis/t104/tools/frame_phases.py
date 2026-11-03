"""T104: per guest frame phases on the frame thread from T98's PT trace.
frame = ref-throttle entry (72E1E0) to the next. Phases: ref wait (72E1E0 dur),
pre = throttle exit -> first ExecutePushBuffer (50D868) of the frame,
emit = first -> last ExecutePushBuffer exit, gap = last 50D868 -> spin entry,
spin = frame-end SPU-job spin (50C818 dur, jobs vs done)."""
import re, statistics as S, sys
f = sys.argv[1]
ev = []
for l in open(f, encoding='utf-8', errors='replace'):
    if not l.startswith('[PT]'): continue
    m = re.match(r'\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=([0-9A-F]+).*?fn=([0-9A-F]+)', l)
    if not m: continue
    d = re.search(r'dur_us=(\d+)', l)
    j = re.search(r'm\[r3\+0x44C\]=([0-9A-F]+) m\[r3\+0x2560\]=([0-9A-F]+)', l)
    ev.append((int(m[1]), int(m[2]), m[3], m[5], int(d[1]) if d else 0, (int(j[1],16), int(j[2],16)) if j else None))
t0, t1 = float(sys.argv[2]) * 1e6, float(sys.argv[3]) * 1e6
ent = [i for i, e in enumerate(ev) if e[3] == '0072E1E0' and e[2] == 'enter' and t0 <= e[0] <= t1]
rows = []
for a, b in zip(ent, ent[1:]):
    seg = ev[a:b]
    T = ev[b][0] - ev[a][0]
    refw = next((e[4] for e in seg if e[3] == '0072E1E0' and e[2] == 'exit'), None)
    pb = [e for e in seg if e[3] == '0050D868']
    sp = [e for e in seg if e[3] == '0050C818']
    if refw is None or not pb or not sp: continue
    tex = next(e[0] for e in seg if e[3] == '0072E1E0' and e[2] == 'exit')
    spin_in = next(e for e in sp if e[2] == 'enter'); spin_out = next((e for e in sp if e[2] == 'exit'), None)
    rows.append(dict(T=T/1e3, ref=refw/1e3, pre=(pb[0][0]-tex)/1e3, emit=(pb[-1][0]-pb[0][0])/1e3,
                     gap=(spin_in[0]-pb[-1][0])/1e3, spin=(spin_out[4] if spin_out else 0)/1e3,
                     jobs=spin_in[5][0] if spin_in[5] else -1, done=spin_in[5][1] if spin_in[5] else -1,
                     pbn=sum(1 for e in pb if e[2]=='enter')))
print(f'frames with all sites: {len(rows)} of {len(ent)-1}')
for k in ('T', 'ref', 'pre', 'emit', 'gap', 'spin', 'pbn', 'jobs', 'done'):
    v = [r[k] for r in rows]
    print(f'{k:5s} median {S.median(v):8.1f}  mean {S.mean(v):8.1f}  p10 {sorted(v)[len(v)//10]:8.1f}  p90 {sorted(v)[len(v)*9//10]:8.1f}')
m = S.mean([r['T'] for r in rows])
for k in ('ref','pre','emit','gap','spin'): print(f'  share {k}: {S.mean([r[k] for r in rows])/m*100:5.1f}%')
