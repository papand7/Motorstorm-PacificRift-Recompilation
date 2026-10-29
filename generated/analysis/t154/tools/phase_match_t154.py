"""T154: phase-matched frame times. The race-start content is deterministic per guest frame (draw_calls per
[rsx-frame-perf] gframe identical across arms), so arms are compared over the same race-frame indices, not
the same host seconds. Race frame 0 = first [rsx-frame-perf] with draw_calls >= 200.
  py -3 phase_match_t154.py <run_dir> ...      prints JSON: per run, per segment, mean wall_ms (RSX wall per
  guest frame = frame interval), fps = 1000 / mean, and the medians of drain / expand / record / other and draws.
Segments: light = race frames 40..499 (1.8-2.5 k draws), heavy = 600..(shortest run's end) (6.8-7.1 k draws)."""
import json, re, statistics as S, sys
from pathlib import Path
RX = re.compile(r'([a-z_]+)=(-?[0-9.]+)')
runs = {}
for rd in map(Path, sys.argv[1:]):
    rows = []
    for l in open(rd / 'stderr.log', encoding='utf-8', errors='replace'):
        if l.startswith('[rsx-frame-perf] gframe='):
            d = {k: float(v) for k, v in RX.findall(l.split('[tex')[0])}
            m = re.search(r'other_ms=([0-9.]+)', l)
            if m: d['other_ms'] = float(m[1])
            rows.append(d)
    i0 = next(i for i, r in enumerate(rows) if r.get('draw_calls', 0) >= 200)
    runs[rd.name] = rows[i0:-1]
end = min(len(r) for r in runs.values())
SEG = {'light': (40, 500), 'heavy': (600, end)}
out = {'race_frames_common': end}
for name, rows in runs.items():
    o = {'race_frames': len(rows)}
    for s, (a, b) in SEG.items():
        seg = rows[a:b]
        w = S.mean(r['wall_ms'] for r in seg)
        o[s] = {'frames': len(seg), 'wall_ms_mean': round(w, 1), 'fps': round(1000 / w, 2),
                **{k: round(S.median(r.get(k, 0) for r in seg), 1) for k in ('draw_calls', 'drain_ms', 'expand_ms', 'record_ms', 'other_ms')}}
    out[name] = o
print(json.dumps(out, indent=1))
