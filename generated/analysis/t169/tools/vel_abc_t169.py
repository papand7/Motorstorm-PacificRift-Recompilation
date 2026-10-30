"""T169: arms A, B, C of the velocity validation: frame statistics on race frames before the capture trigger, last counters, debug-layer counts,
dump and capture metrics. Private images go to img/. Run from this folder (PIL). usage: py -3 vel_abc_t169.py"""
import glob, json, re, statistics as st
from pathlib import Path

import numpy as np
from PIL import Image

T = Path(__file__).resolve().parents[1]
RUNS = T.parents[1] / 'runs'
ARMS = {'A': 'VA', 'B': 'VB', 'C': 'VC'}
num = lambda k, l: float(m[1]) if (m := re.search(k + r'=?\s*([\d.]+)', l)) else 0.0
BOX = {'vehicle': (440, 340, 840, 720), 'terrain': (0, 420, 440, 720), 'far': (300, 180, 980, 400)}


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))] if v else 0


def lap(a):
    y = a.astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    return np.abs(y[1:-1, 1:-1] * 4 - y[:-2, 1:-1] - y[2:, 1:-1] - y[1:-1, :-2] - y[1:-1, 2:])


def frames(log):
    out = []
    for l in log:
        if l.startswith('[rsx-frame-perf]'):
            f = {k: num(k, l) for k in ('gframe', 'wall_ms', 'draw_calls', 'wait_ms', 'rf_ms', 'record_ms', 'submit_ms', 'present_ms', 'drain_ms')}
            m = re.search(r'\| pso ([\d.]+) n=\d+ miss=(\d+) miss_ms=([\d.]+)', l)
            f.update(pso=float(m[1]), miss=int(m[2]), miss_ms=float(m[3])) if m else f.update(pso=0, miss=0, miss_ms=0)
            out.append(f)
    first = next((i for i, f in enumerate(out) if f['draw_calls'] >= 700), None)
    return out[first:] if first is not None else []


res = {}
for a, tag in ARMS.items():
    run = next(RUNS.glob(f'*t169-{a}{tag}'))
    rt = next((T / 'ab').glob(f'runtime-{tag}-*'))
    log = (run / 'stderr.log').read_text('utf-8', 'replace').splitlines()
    tl = [json.loads(l) for l in (rt / 'timeline.jsonl').read_text().splitlines()]
    fr = frames(log)
    print(f'=== {a} {run.name}')
    print('effective', next(l for l in log if l.startswith('[visual] effective')))
    print('last', [l for l in log if l.startswith('[visual-active]')][-1][:360])
    # race frames before the capture trigger: the capture's frame is excluded; elapsed taken from the frames' own wall_ms
    t, keep = 0.0, []
    cap = next(float(x['after_race_s']) for x in tl if x['kind'] == 'vel_capture_trigger') - 1.0
    for f in fr:
        t += f['wall_ms'] / 1000
        if t > cap:
            break
        keep.append(f)
    res[a] = keep
    for name, s in (('all', keep), ('light <2000', [f for f in keep if f['draw_calls'] < 2000]), ('heavy >=4000', [f for f in keep if f['draw_calls'] >= 4000]), ('first 100', keep[:100]), ('after 100', keep[100:])):
        w = [f['wall_ms'] for f in s]
        if w:
            print(f'{name:14s} n={len(w)} FPS {1000 / st.mean(w):5.1f} p50 {pct(w, .5):6.1f} p95 {pct(w, .95):6.1f} p99 {pct(w, .99):6.1f} draws {st.median(f["draw_calls"] for f in s):6.0f} '
                  f'wait~84 {sum(70 < f["wait_ms"] < 100 for f in s):3d} rf {st.mean(f["rf_ms"] for f in s):5.1f} rec {st.mean(f["record_ms"] for f in s):5.1f} pso {st.mean(f["pso"] for f in s):5.1f} '
                  f'miss {sum(f["miss"] for f in s)} miss_ms {sum(f["miss_ms"] for f in s):.0f}')
    print('frames >=500 ms', sum(f['wall_ms'] >= 500 for f in keep), 'max', max(f['wall_ms'] for f in keep))
    print('errors', {k: sum(k in l for l in log) for k in ('Present() Timeout', 'DEVICE_REMOVED', 'access violation', 'NOSYS', 'FATAL', 'resynchron', '[rt-reinterp]')})
    d = json.loads((rt / 'd3d12_messages.json').read_text())
    print('d3d12', {k: v for k, v in d.items() if k != 'other_ods_lines'} if len(str(d)) < 900 else str(d)[:900])
    mem = (rt / 'mem.csv').read_text(errors='replace').splitlines() if (rt / 'mem.csv').exists() else []
    print('mem last', mem[-1][-14:] if mem else None)
    print('wiped velocity snaps:')
    for p in sorted(glob.glob(str(rt / 'rsxi/frames/*/snap*'))):
        im = np.asarray(Image.open(p).convert('RGB'))
        print(' ', Path(p).name, im.shape[1], im.shape[0], 'nonzero %.2f%%' % (np.any(im != 0, axis=2).mean() * 100), 'mean', im.mean(axis=(0, 1)).round(1), 'lap med', float(np.median(lap(im))) if min(im.shape[:2]) > 2 else None)
    dumps = sorted((rt / 'frames').glob('*.bmp'))
    print('dumps', [(p.name, round(float(np.asarray(Image.open(p).convert('L')).mean()), 1)) for p in dumps])

# one sheet of all dumps per arm, for reading the race clock
for a, tag in ARMS.items():
    rt = next((T / 'ab').glob(f'runtime-{tag}-*'))
    dumps = sorted((rt / 'frames').glob('*.bmp'))
    s = Image.new('RGB', (1280, 360 * ((len(dumps) + 1) // 2)))
    for i, p in enumerate(dumps):
        s.paste(Image.open(p).convert('RGB').resize((640, 360)), (640 * (i % 2), 360 * (i // 2)))
    s.save(T / 'img' / f'abc_{a}_sheet.png')
    bb = glob.glob(str(rt / 'rsxi/frames/*/snap*_end_op9999_bb_*'))
    if bb:
        Image.open(bb[0]).convert('RGB').save(T / 'img' / f'abc_{a}_cap_bb.png')
    for p in glob.glob(str(rt / 'rsxi/frames/*/snap*_end_op9999_rt_01650000.bmp')):
        Image.open(p).convert('RGB').save(T / 'img' / f'abc_{a}_cap_vel.png')
