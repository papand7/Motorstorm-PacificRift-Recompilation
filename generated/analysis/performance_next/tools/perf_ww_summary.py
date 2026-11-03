"""performance_next: summarise tools/harness/perf_ww.sh. Per case and arm, over the repeats: median per-frame
texture-recording ms ([rsx-frame-perf] record_ms [tex ... ]), record_ms and draw_cb_ms, skipping the first 2 guest
frames (warm-up: every texture is new). Also the last [tex-cache] wwatch line.
  py -3 perf_ww_summary.py <runs/p dir> [--json out]"""
import json, re, statistics as S, sys
from collections import defaultdict
from pathlib import Path

d = Path(sys.argv[1])
out = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
FP = re.compile(r'gframe=(\d+) .*?draw_cb_ms=([\d.]+).*?record_ms=([\d.]+) \[tex ([\d.]+) n=(\d+)')
res = defaultdict(lambda: defaultdict(list))
ww = {}
for run in sorted(d.iterdir()):
    case, arm, rep = run.name.rsplit('_', 2)
    tex, rec, cb = [], [], []
    for l in open(run / 'err.txt', encoding='utf-8', errors='replace'):
        m = FP.search(l) if l.startswith('[rsx-frame-perf] gframe=') else None
        if m and int(m.group(1)) >= 3:
            cb.append(float(m.group(2))); rec.append(float(m.group(3))); tex.append(float(m.group(4)))
        elif l.startswith('[tex-cache] wwatch'):
            ww[(case, arm)] = l.strip()
    if tex:
        res[(case, arm)]['tex'].append(S.median(tex))
        res[(case, arm)]['rec'].append(S.median(rec))
        res[(case, arm)]['cb'].append(S.median(cb))
rows = []
print(f"{'case':6s} {'arm':6s} {'tex ms (reps)':>28s} {'tex med':>8s} {'record med':>10s} {'draw_cb med':>11s}")
for (case, arm), v in sorted(res.items()):
    r = dict(case=case, arm=arm, tex=v['tex'], tex_med=S.median(v['tex']), rec_med=S.median(v['rec']),
             cb_med=S.median(v['cb']), ww=ww.get((case, arm)))
    rows.append(r)
    print(f"{case:6s} {arm:6s} {' '.join(f'{x:.2f}' for x in v['tex']):>28s} {r['tex_med']:8.2f} {r['rec_med']:10.2f} {r['cb_med']:11.2f}")
if out:
    Path(out).write_text(json.dumps(rows, indent=1), encoding='utf-8')
