"""T162: summarise harness/perf_bench.sh. Per case and arm, over the repeats (median of each run's per-frame medians,
frames >= 3; then median and min..max across repeats):
  cb = [rsx-frame-perf] draw_cb_ms (vertex expansion / gvf writes, the drain-side CPU cost), rec = record_ms,
  rf = rf_ms (whole replay CPU), wall = wall_ms (frame), upload = upload_mb (CPU path vertex bytes), passes;
  gpu = [gpu-prof] gpu_total mean per pass (reports after the first), gvf ring bytes from the final [gvf] line.
  py -3 perf_summary_t162.py <runs/p> [--json out]"""
import json, re, statistics as S, sys
from collections import defaultdict
from pathlib import Path

d = Path(sys.argv[1])
out = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
NUM = re.compile(r'([a-z_]+)=(-?[0-9.]+)')
res = defaultdict(lambda: defaultdict(list))
for run in sorted(d.iterdir()):
    case, arm, rep = run.name.rsplit('_', 2)
    fr = defaultdict(list); gpu = []; rep_n = 0; gvf = None
    for l in open(run / 'err.txt', encoding='utf-8', errors='replace'):
        if l.startswith('[rsx-frame-perf] gframe='):
            v = {k: float(x) for k, x in NUM.findall(l.split(' [tex')[0])}
            if v.get('gframe', 0) >= 3:
                for k in ('draw_cb_ms', 'record_ms', 'rf_ms', 'wall_ms', 'upload_mb', 'passes', 'draw_calls'):
                    fr[k].append(v.get(k, 0.0))
        elif l.startswith('[gpu-prof] report '):
            rep_n += 1
        elif l.startswith('[gpu-prof]   gpu_total') and rep_n > 1:
            gpu.append(float(l.split()[3]))
        elif l.startswith('[gvf] draws='):
            gvf = l.strip()
    if not fr['wall_ms']:
        continue
    r = res[(case, arm)]
    for k, v in fr.items():
        r[k].append(S.median(v))
    if gpu:
        r['gpu_total_ms'].append(S.median(gpu))
    if gvf:
        r['gvf'] = [gvf]
rows = []
print(f"{'case':8s} {'arm':4s} {'cb ms':>16s} {'record':>14s} {'wall':>16s} {'gpu/pass':>16s} {'upload MB':>9s} {'passes':>6s}")
for (case, arm), r in sorted(res.items()):
    def f(k):
        v = r.get(k)
        return (S.median(v), min(v), max(v)) if v else (float('nan'),) * 3
    row = dict(case=case, arm=arm, **{k: f(k) for k in ('draw_cb_ms', 'record_ms', 'rf_ms', 'wall_ms', 'gpu_total_ms', 'upload_mb', 'passes', 'draw_calls')},
               gvf=r.get('gvf', [None])[0])
    rows.append(row)
    g = lambda k: f"{row[k][0]:6.2f} ({row[k][1]:.2f}-{row[k][2]:.2f})"
    print(f"{case:8s} {arm:4s} {g('draw_cb_ms'):>16s} {row['record_ms'][0]:14.2f} {g('wall_ms'):>16s} {g('gpu_total_ms'):>16s} "
          f"{row['upload_mb'][0]:9.1f} {row['passes'][0]:6.0f}")
if out:
    Path(out).write_text(json.dumps(rows, indent=1, default=str), encoding='utf-8')
