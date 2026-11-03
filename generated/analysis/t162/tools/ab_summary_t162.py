#!/usr/bin/env python3
"""T162: per-run summary of the game A/B launches by race window (bench_t161 windows) and frontend.

  py -3 ab_summary_t162.py <run_dir> [...]

For each run: termination, whether the frame clock stalled, frames in the 84 ms GPU-wait mode, window FPS and frame-time
percentiles with the medians of [rsx-frame-perf] (draws, expand, upload, drain, record, tex, wait, other), debug-layer
messages, FIFO resyncs and the last [gvf] counters. Prints JSON."""
import json, re, statistics as S, sys
from collections import defaultdict
from pathlib import Path

F = dict(wall='wall_ms', draws='draw_calls', verts='verts', upload='upload_mb', drain='drain_ms', expand='expand_ms',
         flush='flush_ms', record='record_ms', submit='submit_ms', wait='wait_ms', present='present_ms')


def pct(v, p):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(p / 100 * len(v)))], 1)


def one(rd):
    rd = Path(rd)
    err = (rd / 'stderr.log').read_text(encoding='utf-8', errors='replace').splitlines()
    out = (rd / 'stdout.log').read_text(encoding='utf-8', errors='replace')
    sm = (rd / 'summary.md').read_text(encoding='utf-8', errors='replace')
    fr = []
    gvf = None
    for l in err:
        if l.startswith('[rsx-frame-perf] gframe='):
            d = {k: float(m.group(1)) for k, n in F.items() if (m := re.search(r'\b' + n + r'=([\d.]+)', l))}
            d['g'] = int(re.search(r'gframe=(\d+)', l).group(1))
            m = re.search(r'\[tex ([\d.]+)', l)
            d['tex'] = float(m.group(1)) if m else 0.0
            fr.append(d)
        elif l.startswith('[gvf] draws='):
            gvf = l
    i0 = next((i for i, r in enumerate(fr) if r.get('draws', 0) >= 200), None)
    res = dict(run=rd.name, term=(re.search(r'termination: (.*)', sm) or [None, '?'])[1],
               gc_timeout=out.count('GcKernel::Present() Timeout'), frames=len(fr),
               wait_gt50=sum(r.get('wait', 0) > 50 for r in fr),
               max_draws=max((r.get('draws', 0) for r in fr), default=0),
               debug=sum(bool(re.search(r'sev=[012] ', l)) for l in err), resync=sum('FIFO resync' in l for l in err),
               watchdog=[l[13:] for l in err if '[fc-watchdog] frame clock' in l], gvf=gvf)
    if i0 is None:
        return res
    by, order = defaultdict(list), []
    for r in fr[i0:-1]:
        if r['g'] not in by:
            order.append(r['g'])
        by[r['g']].append(r)
    res['race_frames'] = len(order)
    for name, lo, hi in (('light', 40, 500), ('transition', 500, 600), ('heavy', 600, 900)):
        sel = [by[g] for g in order[lo:hi]]
        if not sel:
            continue
        wall = [sum(p.get('wall', 0) for p in ps) for ps in sel]
        w = dict(frames=len(sel), complete=len(sel) == hi - lo, fps=round(1000 / S.mean(wall), 2), p50=pct(wall, 50),
                 p95=pct(wall, 95), p99=pct(wall, 99))
        for k in ('draws', 'verts', 'upload', 'drain', 'expand', 'flush', 'record', 'tex', 'submit', 'wait'):
            w[k] = round(S.median(sum(p.get(k, 0) for p in ps) for ps in sel), 1)
        res[name] = w
    return res


print(json.dumps([one(a) for a in sys.argv[1:]], indent=1))
