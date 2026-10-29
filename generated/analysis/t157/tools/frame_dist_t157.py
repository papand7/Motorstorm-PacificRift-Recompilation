"""T157: per-guest-frame wall time distribution by race-frame segment (race frame 0 = first [rsx-frame-perf]
with draw_calls >= 200, as t154/tools/phase_match_t154.py). Guest frame wall = sum of its passes' wall_ms.
  [HEAVY_END=<n>] py -3 frame_dist_t157.py <run_dir> ...   prints JSON: per run, per segment, fps (1000/mean), p50/p95/p99 ms,
  medians of the [rsx-frame-perf] fields, and the mean of the same fields."""
import json, re, statistics as S, sys
from collections import OrderedDict
from pathlib import Path
RX = re.compile(r'([a-z_]+)=(-?[0-9.]+)')
def pct(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]
runs = {}
for rd in map(Path, sys.argv[1:]):
    g = OrderedDict()
    for l in open(rd / 'stderr.log', encoding='utf-8', errors='replace'):
        if l.startswith('[rsx-frame-perf] gframe='):
            head, _, br = l.partition('[tex ')
            br, _, tail = br.partition(']')
            d = {k: float(v) for k, v in RX.findall(head + ' ' + tail)}
            m = re.match(r'([0-9.]+) n=(\d+) \| pso ([0-9.]+) n=\d+ miss=(\d+) miss_ms=([0-9.]+) \| cmd ([0-9.]+)', br)
            if m:
                d.update(tex_ms=float(m[1]), tex_n=float(m[2]), pso_ms=float(m[3]), pso_miss=float(m[4]), cmd_ms=float(m[6]))
            g[int(d['gframe'])] = d
    rows = list(g.values())
    i0 = next(i for i, r in enumerate(rows) if r.get('draw_calls', 0) >= 200)
    runs[rd.name] = rows[i0:-1]
end = min(len(r) for r in runs.values())
import os
end = int(os.environ.get('HEAVY_END', end))
SEG = {'light': (40, 500), 'heavy': (600, end)}
FIELDS = ('draw_calls', 'passes', 'verts', 'upload_mb', 'drain_ms', 'draw_cb_ms', 'expand_ms', 'flush_ms', 'miss_ms', 'rf_ms',
          'record_ms', 'tex_ms', 'tex_n', 'pso_ms', 'pso_miss', 'cmd_ms', 'submit_ms', 'wait_ms', 'present_ms', 'other_ms')
out = {'race_frames_common': end}
for name, rows in runs.items():
    o = {}
    for s, (a, b) in SEG.items():
        seg = rows[a:b]; w = [r['wall_ms'] for r in seg]
        if not seg: o[s] = None; continue
        o[s] = {'frames': len(seg), 'fps': round(1000 / S.mean(w), 2), 'wall_mean': round(S.mean(w), 1),
                'p50': round(pct(w, 50), 1), 'p95': round(pct(w, 95), 1), 'p99': round(pct(w, 99), 1),
                'med': {k: round(S.median(r.get(k, 0) for r in seg), 1) for k in FIELDS if any(k in r for r in seg)},
                'mean': {k: round(S.mean(r.get(k, 0) for r in seg), 1) for k in FIELDS if any(k in r for r in seg)}}
    out[name] = o
print(json.dumps(out, indent=1))
