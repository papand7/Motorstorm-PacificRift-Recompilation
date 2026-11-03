"""T171: compare arms A and B: log lines, frame statistics in matching race windows, WPOS draws. usage: py -3 ab_t171.py"""
import json, re
from pathlib import Path

T = Path(__file__).resolve().parents[1]
RUNS = T.parents[1] / 'runs'
WP = {'022CD841', '07200641', '070B0701'}


def num(k, l):
    m = re.search(k + r'=?\s*([\d.]+)', l)
    return float(m[1]) if m else 0.0


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))] if v else 0


for a, tag in (('A', 'TA'), ('B', 'TB')):
    run = next(RUNS.glob(f'*t171-{a}{tag}'))
    rt = next((T / 'ab').glob(f'runtime-{tag}-*'))
    log = (run / 'stderr.log').read_text('utf-8', 'replace').splitlines()
    tl = [json.loads(l) for l in (rt / 'timeline.jsonl').read_text().splitlines()]
    print(f'=== {a} {run.name}')
    print('stop', [x['why'] for x in tl if x['kind'] == 'stop'], 'serious', [x['line'][:120] for x in tl if x['kind'] == 'serious'])
    print('race_entry', [x['host_s'] for x in tl if x['kind'] == 'race_entry'], 'presses', [(x['host_s'], x['step']) for x in tl if x['kind'] == 'press'])
    print('[WPOS]', len([l for l in log if l.startswith('[WPOS]')]))
    for l in [l for l in log if l.startswith('[WPOS]')][:10]:
        print('  ', l[:170])
    for k in ('compile FAIL', 'PSO fail', 'CreateGraphicsPipelineState failed', 'Present() Timeout', 'E_INVALIDARG'):
        print(f'  count {k!r}:', sum(k in l for l in log))
    fp = [l for l in log if '[rsx-frame-perf]' in l]
    fr = []
    for l in fp:
        f = {k: num(k, l) for k in ('gframe', 'wall_ms', 'draw_calls', 'wait_ms', 'rf_ms', 'record_ms', 'submit_ms', 'present_ms', 'drain_ms')}
        m = re.search(r'\| pso ([\d.]+) n=\d+ miss=(\d+) miss_ms=([\d.]+)', l)
        f.update(pso=float(m[1]), miss=int(m[2]), miss_ms=float(m[3])) if m else f.update(pso=0, miss=0, miss_ms=0)
        fr.append(f)
    first = next((i for i, f in enumerate(fr) if f['draw_calls'] >= 700), None)
    race = fr[first:] if first is not None else []
    cap = next(float(x['after_race_s']) for x in tl if x['kind'] == 'vel_capture_trigger') - 1.0
    t, keep = 0.0, []
    for f in race:
        t += f['wall_ms'] / 1000
        if t < cap:
            f['t'] = t
            keep.append(f)
    print('frame-perf lines', len(fp), 'race frames before capture', len(keep), 'first gframe', keep[0]['gframe'] if keep else None, 'last', keep[-1]['gframe'] if keep else None)

    def stat(name, s):
        if not s:
            print(' ', name, 'none'); return
        w = [f['wall_ms'] for f in s]
        print(f"  {name}: n={len(s)} fps={1000 * len(s) / sum(w):.2f} p50={pct(w, .5):.1f} p95={pct(w, .95):.1f} p99={pct(w, .99):.1f} max={max(w):.1f} "
              f"draws={sum(f['draw_calls'] for f in s) / len(s):.0f} rf={sum(f['rf_ms'] for f in s) / len(s):.1f} wait={sum(f['wait_ms'] for f in s) / len(s):.1f} "
              f"present={sum(f['present_ms'] for f in s) / len(s):.1f} miss={sum(f['miss'] for f in s)} miss_ms={sum(f['miss_ms'] for f in s):.0f} >100ms={sum(x > 100 for x in w)}")
    stat('all race', keep)
    stat('t 0-15 s', [f for f in keep if f['t'] < 15])
    stat('t 15-37 s', [f for f in keep if f['t'] >= 15])
    stat('heavy >=1200 draws', [f for f in keep if f['draw_calls'] >= 1200])
    stat('light <1200 draws', [f for f in keep if f['draw_calls'] < 1200])
    allm = sum(f['miss'] for f in fr)
    print('  all-session PSO misses', allm, 'miss_ms', round(sum(f['miss_ms'] for f in fr)))
    print('  slow', [l[:120] for l in log if l.startswith('[slow') or 'render thread stall' in l][:5])
    d = rt / 'd3d12_messages.json'
    print('  d3d12', d.read_text()[:700].replace('\n', ' ') if d.exists() else None)
    print('  spurs-busy lines', sum(l.startswith('[spurs-busy]') for l in log))
    va = [l for l in log if l.startswith('[visual-active]')]
    print('  last active', va[-1][:300] if va else None)
    dirs = sorted((rt / 'rsxi' / 'frames').iterdir())
    for fd in dirs:
        ev = fd / 'events.jsonl'
        rows = [json.loads(l) for l in ev.read_text('utf-8', 'replace').splitlines() if l.strip().startswith('{')]
        print('  capture', fd.name, 'events', len(rows), 'snaps', len(list(fd.glob('snap*.bmp'))))
        seen = {}
        for i, r in enumerate(rows):
            f = str(r.get('fp', r.get('fp_hash', ''))).upper().replace('0X', '').zfill(8)
            if f in WP:
                seen.setdefault(f, []).append((r.get('op', i), r.get('wpos_remap'), r.get('shader_window'), r.get('blend'), r.get('rt', r.get('rt_addr'))))
        print('    WPOS draws', {k: (len(v), v[:3]) for k, v in seen.items()})
        print('    sample keys', sorted(rows[min(50, len(rows) - 1)].keys())[:30])
    print('  frames', sorted(p.name for p in (rt / 'frames').glob('*.bmp')))
