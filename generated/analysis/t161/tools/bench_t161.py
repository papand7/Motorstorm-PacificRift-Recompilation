#!/usr/bin/env python3
"""T161: one-run race-benchmark summary (py -3 bench_t161.py <run_dir> [--heavy-lo 600 --heavy-hi 900]).

Race frame 0 = first [rsx-frame-perf] with draw_calls >= 200 (T154). Windows by race-frame index:
  warmup 0-39 (shader/PSO compiles, excluded), light 40-499, transition 500-599 (compiles), heavy 600-hi.
Per window: frames, FPS (1000 / mean frame interval), p50/p95/p99 frame time, median draw calls,
RSX passes per frame, median drain/record/other ms, shader/PSO compile ms.
Validity: each window is 'complete' only if every frame index in it was logged.
Load attribution: [sc-wait] and (T161) [hle-wait] totals per thread and key over a host-time span
given by the [rsx-hb] ms= clock (--wait-span A:B seconds; default: whole run)."""
import json, re, statistics as S, sys
from collections import defaultdict

RX = re.compile(r'([a-z_]+)=(-?[0-9.]+)')
WAIT = re.compile(r'\[(sc|hle)-wait\] window_ms=\d+ tid=(\d+) total_ms=[\d.]+(.*)')
KEY = re.compile(r' (sc\d+|nid[0-9A-F]{8})=([\d.]+)ms/(\d+)')
HB = re.compile(r'\[rsx-hb\] ms=(\d+)')
NIDS = {'1573DC3F': 'sys_lwmutex_lock', '2A6D9D51': 'sys_lwcond_wait', '4D5FF8E2': 'cellFsRead',
        '718BF5F8': 'cellFsOpen', 'A397D042': 'cellFsLseek', '9FDBBFE0': 'cellFsAioRead'}


def pct(v, p):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(p / 100 * len(v)))], 1)


def parse(lines, span=None):
    frames, waits, host_s = [], defaultdict(lambda: [0.0, 0]), 0.0
    for l in lines:
        m = HB.match(l)
        if m:
            host_s = int(m.group(1)) / 1000.0
            continue
        if l.startswith('[rsx-frame-perf] gframe='):
            d = {k: float(v) for k, v in RX.findall(l.split('[tex')[0])}
            m = re.search(r'pso [\d.]+ n=\d+ miss=\d+ miss_ms=([\d.]+)', l)
            vs = re.search(r'vs=\S+ miss_ms=([\d.]+)', l)
            d['compile_ms'] = (float(m.group(1)) if m else 0.0) + (float(vs.group(1)) if vs else 0.0)
            m = re.search(r'other_ms=([0-9.]+)', l)
            if m:
                d['other_ms'] = float(m.group(1))
            frames.append(d)
            continue
        m = WAIT.match(l)
        if m and (span is None or span[0] <= host_s < span[1]):
            for k, ms, n in KEY.findall(m.group(3)):
                name = 'hle:' + NIDS.get(k[3:], k) if k.startswith('nid') else k
                w = waits[(int(m.group(2)), name)]
                w[0] += float(ms)
                w[1] += int(n)
    return frames, waits


def windows(frames, heavy=(600, 900)):
    i0 = next((i for i, r in enumerate(frames) if r.get('draw_calls', 0) >= 200), None)
    if i0 is None:
        return {'race_frames': 0}
    # The last line may be a partial frame at the stop; drop it.
    race = frames[i0:-1]
    # Guest frames span several RSX passes: group by gframe (first pass carries wall_ms).
    by_g, order = defaultdict(list), []
    for r in race:
        g = int(r.get('gframe', -1))
        if g not in by_g:
            order.append(g)
        by_g[g].append(r)
    out = {'race_frames': len(order)}
    for name, lo, hi in (('warmup', 0, 40), ('light', 40, 500), ('transition', 500, 600), ('heavy', *heavy)):
        sel = [by_g[g] for g in order[lo:hi]]
        if not sel:
            out[name] = {'frames': 0, 'complete': False}
            continue
        wall = [sum(p.get('wall_ms', 0.0) for p in ps) for ps in sel]
        first = [ps[0] for ps in sel]
        mean = S.mean(wall)
        out[name] = {
            'frames': len(sel), 'complete': len(sel) == hi - lo,
            'fps': round(1000.0 / mean, 2) if mean > 0 else None,
            'p50_ms': pct(wall, 50), 'p95_ms': pct(wall, 95), 'p99_ms': pct(wall, 99),
            'draw_calls_med': S.median(sum(p.get('draw_calls', 0) for p in ps) for ps in sel),
            'passes_med': S.median(len(ps) for ps in sel),
            'drain_ms_med': round(S.median(sum(p.get('drain_ms', 0) for p in ps) for ps in sel), 1),
            'record_ms_med': round(S.median(sum(p.get('record_ms', 0) for p in ps) for ps in sel), 1),
            'other_ms_med': round(S.median(f.get('other_ms', 0) for f in first), 1),
            'compile_ms': round(sum(p['compile_ms'] for ps in sel for p in ps), 1),
        }
    return out


def main(argv):
    rd, heavy, span = argv[0], (600, 900), None
    if '--heavy-hi' in argv:
        heavy = (heavy[0], int(argv[argv.index('--heavy-hi') + 1]))
    if '--heavy-lo' in argv:
        heavy = (int(argv[argv.index('--heavy-lo') + 1]), heavy[1])
    if '--wait-span' in argv:
        a, b = argv[argv.index('--wait-span') + 1].split(':')
        span = (float(a), float(b))
    with open(rd + '/stderr.log', encoding='utf-8', errors='replace') as f:
        frames, waits = parse(f, span)
    res = windows(frames, heavy)
    top = sorted(waits.items(), key=lambda kv: -kv[1][0])[:20]
    res['waits_top'] = [{'tid': t, 'key': k, 'ms': round(v[0], 1), 'calls': v[1]} for (t, k), v in top]
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main(sys.argv[1:])
