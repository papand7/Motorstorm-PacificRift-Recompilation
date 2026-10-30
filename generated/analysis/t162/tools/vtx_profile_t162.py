"""T162: vertex-path profile of one run from its [rsx-frame-perf] lines (no new instrumentation).
Race frame 0 = first guest frame with >= 200 draw calls (as t161/tools/bench_t161.py); light = race frames 40-499,
heavy = 600-hi. Per guest frame the passes are summed; the window reports medians per guest frame.
  py -3 vtx_profile_t162.py <run_dir> [--heavy-hi N] [--json out]"""
import json, re, statistics as S, sys
from collections import defaultdict
from pathlib import Path

rd = Path(sys.argv[1])
hi = int(sys.argv[sys.argv.index('--heavy-hi') + 1]) if '--heavy-hi' in sys.argv else 900
out = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
NUM = re.compile(r'([a-z_]+)=(-?[0-9.]+)')
REC = re.compile(r'record_ms=([\d.]+) \[tex ([\d.]+) n=(\d+) \| pso ([\d.]+) n=(\d+) miss=(\d+) miss_ms=([\d.]+) \| cmd ([\d.]+)\]')
frames = []
for l in open(rd / 'stderr.log', encoding='utf-8', errors='replace'):
    if not l.startswith('[rsx-frame-perf] gframe='):
        continue
    d = {k: float(v) for k, v in NUM.findall(l.split(' [tex')[0])}
    m = REC.search(l)
    if m:
        d.update(rec_tex=float(m.group(2)), rec_pso=float(m.group(4)), pso_miss_ms=float(m.group(7)), rec_cmd=float(m.group(8)))
    frames.append(d)
i0 = next(i for i, r in enumerate(frames) if r.get('draw_calls', 0) >= 200)
by, order = defaultdict(list), []
for r in frames[i0:-1]:
    g = int(r['gframe'])
    if g not in by:
        order.append(g)
    by[g].append(r)
KEYS = ['draw_calls', 'verts', 'upload_mb', 'drain_ms', 'draw_cb_ms', 'expand_ms', 'flush_ms', 'rf_ms', 'record_ms',
        'rec_tex', 'rec_pso', 'pso_miss_ms', 'rec_cmd', 'submit_ms', 'wait_ms', 'present_ms', 'wall_ms']
res = {'run': str(rd), 'race_frames': len(order)}
for name, lo, h in (('light', 40, 500), ('heavy', 600, hi)):
    sel = [by[g] for g in order[lo:h]]
    if not sel:
        continue
    w = {'frames': len(sel), 'passes_med': S.median(len(p) for p in sel)}
    for k in KEYS:
        w[k] = round(S.median(sum(p.get(k, 0.0) for p in ps) for ps in sel), 2)
    w['bytes_per_vert'] = round(w['upload_mb'] * 1048576 / w['verts'], 1) if w['verts'] else None
    w['verts_per_draw'] = round(w['verts'] / w['draw_calls'], 1) if w['draw_calls'] else None
    res[name] = w
s = json.dumps(res, indent=1)
print(s)
if out:
    Path(out).write_text(s, encoding='utf-8')
