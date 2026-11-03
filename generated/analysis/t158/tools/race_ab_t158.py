"""T158: race-frame-indexed comparison of two runs (A = baseline, B = candidate).
  py -3 race_ab_t158.py <run_A> <run_B> [lo hi]     prints JSON
Race frame 0 = first [rsx-frame-perf] with draw_calls >= 200 (as phase_match_t154.py). Window default 40..500
(light scene). Per run: frames, mean/median/p95/p99 wall_ms (frame interval), fps = 1000 / mean, medians of
drain/expand/record/other. Correctness: per-frame draw_calls and vertex-ish counters compared index by index."""
import json, re, statistics as S, sys
RX = re.compile(r'([a-z_]+)=(-?[0-9.]+)')


def rows(rd):
    out = []
    for l in open(rd + '/stderr.log', encoding='utf-8', errors='replace'):
        if l.startswith('[rsx-frame-perf] gframe='):
            d = {k: float(v) for k, v in RX.findall(l.split('[tex')[0])}
            m = re.search(r'other_ms=([0-9.]+)', l)
            if m: d['other_ms'] = float(m[1])
            out.append(d)
    i0 = next(i for i, r in enumerate(out) if r.get('draw_calls', 0) >= 200)
    return out[i0:-1]


def pct(v, p):
    v = sorted(v); return round(v[min(len(v) - 1, int(p / 100 * len(v)))], 1)


a, b = sys.argv[1], sys.argv[2]
lo, hi = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (40, 500)
R = {a: rows(a), b: rows(b)}
res = {'window': [lo, hi]}
for rd, rs in R.items():
    seg = rs[lo:hi]
    w = [r['wall_ms'] for r in seg]
    res[rd.rstrip('/').split('/')[-1]] = {
        'race_frames': len(rs), 'frames': len(seg), 'fps': round(1000 / S.mean(w), 2),
        'wall_ms_mean': round(S.mean(w), 1), 'p50': pct(w, 50), 'p95': pct(w, 95), 'p99': pct(w, 99),
        **{k: round(S.median(r.get(k, 0) for r in seg), 1) for k in ('drain_ms', 'expand_ms', 'record_ms', 'other_ms', 'draw_calls')}}
keys = [k for k in R[a][0] if k not in ('wall_ms', 'drain_ms', 'expand_ms', 'record_ms', 'other_ms') and not k.endswith('_ms') and not k.endswith('_us')]
n = min(len(R[a]), len(R[b]))
diff = {k: sum(1 for i in range(n) if R[a][i].get(k) != R[b][i].get(k)) for k in keys}
res['per_frame_mismatch_counts'] = {'compared_frames': n, **diff}
print(json.dumps(res, indent=1))
