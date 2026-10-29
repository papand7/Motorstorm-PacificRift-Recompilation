"""T153: performance-matrix rows from the A/B analyses (game runs only; nothing is estimated).

  py -3 matrix_t153.py            reads t153/ab/ana_<tag>.json (tag = <arm>r<n>, from ana_t153.py), prints markdown

Per arm: runs, race FPS (median of runs, and each run), frame ms p50/p95/p99, RSX CPU ms (drain + rf of
[rsx-frame-perf]), snapshot ms (tex-snapshot-stats total), expand ms, frame-clock idle (other_ms), PPU frame-thread
ms and critical-path gate (t149 cpath), race entry and whether the trace covered the race. Missing = '—'."""
import json, re, statistics as S
from pathlib import Path

AB = Path(__file__).resolve().parents[1] / 'ab'
ORDER = 'APZBCDE'


def g(d, *ks):
    for k in ks:
        if not isinstance(d, dict) or k not in d or d[k] is None:
            return None
        d = d[k]
    return d


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(S.median(xs), 2) if xs else None


def f(x):
    return '—' if x is None else (f'{x:.2f}' if isinstance(x, float) else str(x))


rows = {}
for p in sorted(AB.glob('ana_*.json')):
    m = re.fullmatch(r'ana_([A-Z])r(\d+)\.json', p.name)
    if m:
        rows.setdefault(m[1], []).append(json.loads(p.read_text(encoding='utf-8')))
print('| Arm | runs | FPS median (runs) | frame ms p50/p95/p99 | RSX CPU ms (drain+rf) | snapshot ms | expand ms '
      '| frame-clock idle ms | PPU frame thread running ms | top gate | race entry s | trace covers race |')
print('|---|---:|---|---|---:|---:|---:|---:|---:|---|---|---|')
for a in sorted(rows, key=ORDER.index):
    r = rows[a]
    fps = [g(x, 'fps', 'fps') for x in r]
    pct = [g(x, 'fps', 'frame_ms_p50_p95_p99_max') for x in r]
    p3 = ['/'.join(f(v) for v in p[:3]) if isinstance(p, list) else '—' for p in pct]
    rsx = [None if g(x, 'rsx_frame_perf', 'drain_ms') is None or g(x, 'rsx_frame_perf', 'rf_ms') is None
           else g(x, 'rsx_frame_perf', 'drain_ms') + g(x, 'rsx_frame_perf', 'rf_ms') for x in r]
    ft = [g(x, 'cpath', 'frame_thread') for x in r]
    ftm = med([v.get('running_ms') if isinstance(v, dict) else None for v in ft])
    gates = [g(x, 'cpath', 'critical', 'gates') for x in r]
    gate = ', '.join(max(d, key=d.get) for d in gates if isinstance(d, dict) and d) or '—'
    print(f"| {a} | {len(r)} | {f(med(fps))} ({', '.join(f(v) for v in fps)}) | {'; '.join(p3)} | {f(med(rsx))} "
          f"| {f(med([g(x, 'tex_snapshot', 'total') for x in r]))} | {f(med([g(x, 'rsx_frame_perf', 'expand_ms') for x in r]))} "
          f"| {f(med([g(x, 'rsx_frame_perf', 'other_ms') for x in r]))} | {f(ftm)} "
          f"| {gate} "
          f"| {', '.join(f(g(x, 'race_entry_s')) for x in r)} | {', '.join(str(x.get('trace_covers_race')) for x in r)} |")
if not rows:
    print('| (no authorised game runs yet) | | | | | | | | | | | |')
