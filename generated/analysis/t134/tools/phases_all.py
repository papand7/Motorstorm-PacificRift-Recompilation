"""T134: per-guest-frame main-thread phases (T104/T106 definitions) for every T122 and T106 A/B run.
frame = 72E1E0 entry to the next on tid 1; ref = 72E1E0 duration; pre = ref exit -> first 50D868;
emit = first -> last 50D868; gap = last 50D868 -> 50C818 entry; spin = 50C818 duration.
Window = [last PT t - 85 s, last PT t - 15 s] (runner stops at race entry + 90 s).
  py -3 phases_all.py > phases_all.txt"""
import re, statistics as S, sys, json
from pathlib import Path
RUNS = Path(__file__).resolve().parents[3] / 'runs'
RX = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=[0-9A-F]+.*?fn=([0-9A-F]+)')
def phases(log):
    ev = []
    for l in open(log, encoding='utf-8', errors='replace'):
        if not l.startswith('[PT] t='): continue
        m = RX.match(l)
        if not m or m[2] != '1': continue
        d = re.search(r'dur_us=(\d+)', l)
        ev.append((int(m[1]), m[3], m[4], int(d[1]) if d else 0))
    if not ev: return None
    tmax = ev[-1][0]; t0, t1 = tmax - 85e6, tmax - 15e6
    ent = [i for i, e in enumerate(ev) if e[2] == '0072E1E0' and e[1] == 'enter' and t0 <= e[0] <= t1]
    rows = []
    for a, b in zip(ent, ent[1:]):
        seg = ev[a:b]
        rx = next((e for e in seg if e[2] == '0072E1E0' and e[1] == 'exit'), None)
        pb = [e for e in seg if e[2] == '0050D868']
        si = next((e for e in seg if e[2] == '0050C818' and e[1] == 'enter'), None)
        so = next((e for e in seg if e[2] == '0050C818' and e[1] == 'exit'), None)
        if not rx or not pb or not si: continue
        rows.append(dict(T=(ev[b][0] - ev[a][0]) / 1e3, ref=rx[3] / 1e3, pre=(pb[0][0] - rx[0]) / 1e3,
                         emit=(pb[-1][0] - pb[0][0]) / 1e3, gap=(si[0] - pb[-1][0]) / 1e3, spin=(so[3] if so else 0) / 1e3))
    return rows
out = {}
for r in sorted(RUNS.glob('*-t1[02][62]-ab-*')):
    rows = phases(r / 'stderr.log') if (r / 'stderr.log').exists() else None
    if not rows: continue
    m = {k: round(S.mean([x[k] for x in rows]), 1) for k in ('T', 'ref', 'pre', 'emit', 'gap', 'spin')}
    m['p50'] = round(S.median([x['T'] for x in rows]), 1); m['n'] = len(rows)
    out[r.name] = m
    print(f"{r.name.split('-ab-')[0][-6:]} {r.name.split('-ab-')[1]:6s} n={m['n']:4d} T={m['T']:6.1f} p50={m['p50']:6.1f} ref={m['ref']:5.1f} pre={m['pre']:6.1f} emit={m['emit']:5.1f} gap={m['gap']:5.1f} spin={m['spin']:5.1f}")
(Path(__file__).parent.parent / 'phases_all.json').write_text(json.dumps(out, indent=1))
