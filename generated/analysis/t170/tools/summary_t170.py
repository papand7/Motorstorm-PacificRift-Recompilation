"""T170: one launch's results: race frames (first frame with at least 200 draw calls, as run_guard_t167), light < 3,000 records, heavy >= 5,000,
stage means per class and per 10 s of game time since race entry, CPU per thread and system, other processes, GPU memory, and log checks.
usage: py -3 summary_t170.py <runtime dir> [...]"""
import json, re, statistics as st, sys
from pathlib import Path

RX = re.compile(r'\[rsx-frame-perf\] gframe=(\d+) pass=\d+ wall_ms=([\d.]+) \| passes=(\d+) early=\d+ records=(\d+) draw_calls=(\d+) verts=(\d+) upload_mb=([\d.]+) \| '
                r'drain_ms=([\d.]+) draw_cb_ms=([\d.]+) expand_ms=([\d.]+) flush_ms=([\d.]+) vs=(\d+)/(\d+) miss_ms=([\d.]+) \| '
                r'rf_ms=([\d.]+) \(in_drain ([\d.]+)\) record_ms=([\d.]+) \[tex ([\d.]+) n=\d+ \| pso ([\d.]+) n=\d+ miss=(\d+) miss_ms=([\d.]+) \| cmd ([\d.]+)\] '
                r'submit_ms=([\d.]+) wait_ms=([\d.]+) present_ms=([\d.]+) \| other_ms=([\d.]+)')
F = ('gf', 'wall', 'passes', 'rec', 'calls', 'verts', 'up', 'drain', 'cb', 'expand', 'flush', 'vsm', 'vsn', 'vsmiss', 'rf', 'rfd', 'record', 'tex', 'pso', 'psomiss', 'psomissms', 'cmd', 'submit', 'wait', 'present', 'other')
BAD = re.compile(r'pso_fail|PSO creation FAIL|DEVICE_REMOVED|DeviceRemoved|device removed|E_INVALIDARG|Gc ERROR|ACCESS_VIOLATION|access violation|Present\(\) Timeout|FIFO resync|Present failed|compile FAIL', re.I)


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))]


def row(name, fr):
    if not fr:
        print(f'  {name:14s} n=0')
        return
    w = [f['wall'] for f in fr]
    m = lambda k: st.mean(f[k] for f in fr)
    print(f'  {name:14s} n={len(fr):5d} fps={1000 / st.mean(w):5.1f} mean={st.mean(w):6.1f} p50={pct(w, .5):6.1f} p95={pct(w, .95):6.1f} p99={pct(w, .99):6.1f} max={max(w):7.1f} | '
          f'rec={st.median(f["rec"] for f in fr):5.0f} calls={st.median(f["calls"] for f in fr):5.0f} upMB={m("up"):5.1f} | drain={m("drain"):5.1f} expand={m("expand"):5.1f} rf={m("rf"):5.1f} record={m("record"):5.1f} '
          f'tex={m("tex"):4.1f} pso={m("pso"):4.1f} cmd={m("cmd"):5.1f} submit={m("submit"):4.1f} wait={m("wait"):5.1f} present={m("present"):4.1f} other={m("other"):5.1f} | psomiss={sum(f["psomiss"] for f in fr):.0f} missms={sum(f["psomissms"] for f in fr):.0f} vsmiss={sum(f["vsm"] for f in fr):.0f}')


for rt in map(Path, sys.argv[1:]):
    wr = (rt / 'wrapper.log').read_text()
    run = Path(re.search(r'run_dir=(.*?) leftover', wr).group(1))
    print('==', rt.name, '|', re.search(r'sha256=(\w+)', wr).group(1), '|', re.search(r'end .*', wr).group(0)[:90])
    t = (run / 'stderr.log').read_text('utf-8', 'replace').splitlines()
    fr = []
    for l in t:
        m = RX.search(l)
        if m:
            fr.append(dict(zip(F, map(float, m.groups()))))
    tl = [json.loads(l) for l in (rt / 'timeline.jsonl').read_text().splitlines()]
    entry = next((r for r in tl if r['kind'] == 'race_entry'), None)
    print('  race entry host s', entry and entry['host_s'], '| frames total', len(fr), '| config', [r['line'][:110] for r in tl if r['kind'] == 'config'])
    print('  pad', [(r['host_s'], r.get('step')) for r in tl if r['kind'] == 'press'])
    first = next((i for i, f in enumerate(fr) if f['calls'] >= 200), None)
    if first is None:
        print('  never in race')
        continue
    race = fr[first:]
    print('  race gframes', race[0]['gf'], race[-1]['gf'], 'n', len(race), 'game s', round(sum(f['wall'] for f in race) / 1000, 1))
    row('race all', race)
    row('light<3000', [f for f in race if f['rec'] < 3000])
    row('mid', [f for f in race if 3000 <= f['rec'] < 5000])
    row('heavy>=5000', [f for f in race if f['rec'] >= 5000])
    c, k, b = 0.0, 0, []
    for f in race:
        c += f['wall'] / 1000
        if c >= (k + 1) * 10:
            row(f'{k * 10}-{(k + 1) * 10}s', b)
            k, b = k + 1, []
        b.append(f)
    row(f'{k * 10}s-end', b)
    print('  perf-deep'); [print('   ', l[:420]) for l in t if l.startswith('[perf-deep] gf=')][-3:]
    g = [l for l in t if l.startswith('[gpu-prof]')]
    print('  gpu-prof', len(g)); [print('   ', l[:300]) for l in g[-3:]]
    s = [l for l in t if l.startswith('[sc-wait') or 'sc_wait' in l[:24]]
    print('  sc-wait', len(s)); [print('   ', l[:300]) for l in s[-2:]]
    bad = [l for l in t if BAD.search(l)]
    print('  bad lines', len(bad)); [print('   ', l[:170]) for l in bad[:8]]
    print('  debug layer lines', sum('debug layer' in l.lower() for l in t), '| vp-parallel', [l for l in t if l.startswith('[vp-parallel]')][:2], '| visual', [l[:150] for l in t if l.startswith('[visual] effective')][:1])
    print('  frames dumped', len(list((rt / 'frames').glob('*.bmp'))))
    cj = [json.loads(l) for l in (rt / 'cpu.jsonl').read_text().splitlines() if '"t"' in l]
    if entry:
        cj = [c_ for c_ in cj if c_['t'] >= entry['wall']]
    if len(cj) >= 2:
        a, z = cj[0], cj[-1]
        dt = z['t'] - a['t']
        top = sorted(((z['threads'][k_] - a['threads'].get(k_, 0)) / dt, k_) for k_ in z['threads'])[::-1][:10]
        tot = sum(z['threads'][k_] - a['threads'].get(k_, 0) for k_ in z['threads']) / dt
        print(f'  CPU race {dt:.0f} s: game {tot:.2f} cores, threads {len(z["threads"])}, top', [(tid, round(v, 2)) for v, tid in top])
        print(f'  system busy {(z["sys_busy"] - a["sys_busy"]) / dt:.2f} cores, idle {(z["sys_idle"] - a["sys_idle"]) / dt:.2f}')
        o = {}
        for c_ in cj:
            for n, p, v in c_['others']:
                o[n] = o.get(n, 0) + v
        print('  others CPU s', sorted(((round(v, 1), n) for n, v in o.items()), reverse=True)[:8], '| max game pids', max(len(c_['game_pids']) for c_ in cj))
    g = (rt / 'gpu.csv').read_text().splitlines() if (rt / 'gpu.csv').exists() else []
    if g:
        print('  gpu', g[0].split(',')[1], '| mem MiB max', max(int(x.split(',')[3].split()[0]) for x in g), '| util% p50', pct([int(x.split(',')[2].split()[0]) for x in g], .5))
