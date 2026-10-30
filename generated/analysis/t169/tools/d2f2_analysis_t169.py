"""T169: D2/F2 (optionally D1/F1): frame-time and work statistics aligned on the first race frame, the draw-binned comparison, the dump
metrics and the dump pairing by image similarity. Run from generated/analysis/t169/tools (PIL). usage: py -3 d2f2_analysis_t169.py"""
import json, re, statistics as st
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

T = Path(__file__).resolve().parents[1]
RUNS = T.parents[1] / 'runs'
ARMS = {'D2': '20261030-175939-t169-DD2', 'F2': '20261030-180259-t169-FF2', 'D1': '20261030-171540-t169-DD1', 'F1': None}
for p in RUNS.glob('*t169-FF1'):
    ARMS['F1'] = p.name
RT = {'D2': next((T / 'ab').glob('runtime-D2-*')), 'F2': next((T / 'ab').glob('runtime-F2-*'))}
num = lambda k, l: float(m[1]) if (m := re.search(k + r'=?\s*([\d.]+)', l)) else 0.0


def frames(run):
    out = []
    for l in (RUNS / run / 'stderr.log').read_text('utf-8', 'replace').splitlines():
        if l.startswith('[rsx-frame-perf]'):
            f = {k: num(k, l) for k in ('gframe', 'wall_ms', 'draw_calls', 'records', 'upload_mb', 'drain_ms', 'rf_ms', 'record_ms', 'submit_ms', 'wait_ms', 'present_ms')}
            m = re.search(r'\[tex ([\d.]+) n=\d+ \| pso ([\d.]+) n=\d+ miss=(\d+) miss_ms=([\d.]+) \| cmd ([\d.]+)\]', l)
            f.update(tex=float(m[1]), pso=float(m[2]), miss=int(m[3]), miss_ms=float(m[4]), cmd=float(m[5])) if m else f.update(tex=0, pso=0, miss=0, miss_ms=0, cmd=0)
            out.append(f)
    first = next((i for i, f in enumerate(out) if f['draw_calls'] >= 700), None)
    return out[first:] if first is not None else []


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))] if v else 0


def row(name, fr):
    if not fr:
        return f'| {name} | 0 | | | | | | | | | | | | |'
    w = [f['wall_ms'] for f in fr]
    mean = lambda k: st.mean(f[k] for f in fr)
    return (f'| {name} | {len(fr)} | {1000 / st.mean(w):.1f} | {pct(w, .5):.1f} | {pct(w, .95):.1f} | {pct(w, .99):.1f} | {st.median(f["draw_calls"] for f in fr):.0f} | {mean("rf_ms"):.1f} | '
            f'{mean("record_ms"):.1f} | {mean("tex"):.1f} | {mean("pso"):.1f} | {mean("cmd"):.1f} | {mean("submit_ms"):.1f} | {mean("wait_ms"):.1f} | {mean("present_ms"):.1f} | {sum(f["miss"] for f in fr)} | {sum(f["miss_ms"] for f in fr):.0f} | {mean("upload_mb"):.2f} |')


HEAD = '| window | n | FPS | p50 | p95 | p99 | draws | rf | record | tex | pso | cmd | submit | wait | present | PSO miss | miss ms | upload MB |\n|---|' + '---|' * 17
F = {k: frames(v) for k, v in ARMS.items() if v}
print(HEAD)
for k, fr in F.items():
    print(row(f'{k} all race', fr))
for lo, hi in ((0, 100), (100, 200), (200, 300), (300, 400), (400, 500)):
    for k in ('D2', 'F2'):
        print(row(f'{k} race frames {lo}-{hi}', F[k][lo:hi]))
for lo, hi in ((700, 2000), (2000, 3500), (3500, 5000), (5000, 7000), (7000, 99999)):
    for k in ('D2', 'F2'):
        print(row(f'{k} draws {lo}-{hi}', [f for f in F[k] if lo <= f['draw_calls'] < hi]))
a, b = [f['draw_calls'] for f in F['D2']], [f['draw_calls'] for f in F['F2']]
n = min(len(a), len(b))
print('race frames', len(a), len(b), 'identical draw counts per frame index', sum(x == y for x, y in zip(a, b)), 'of', n, 'corr', round(float(np.corrcoef(a[:n], b[:n])[0, 1]), 3))
print('wait ~84 frames', {k: sum(70 < f['wait_ms'] < 100 for f in fr) for k, fr in F.items()})
for k in ('D2', 'F2'):
    log = (RUNS / ARMS[k] / 'stderr.log').read_text('utf-8', 'replace').splitlines()
    print(k, 'c33 x last', next((l[:90] for l in reversed(log) if l.startswith('[vpc-watch]')), ''))
    print(k, 'spurs-busy lines', sum(l.startswith('[spurs-busy]') for l in log))
    print(k, 'vis-work total', {w: sum(int(m[1]) for l in log if l.startswith('[vis-work]') and (m := re.search(w + r'=(\d+)', l))) for w in ('samplers_new', 'sampler_binds', 'uploads', 'upload_bytes', 'compiles')})
    va = [l for l in log if l.startswith('[visual-active]')]
    print(k, 'first active', va[0][:300] if va else '')
    print(k, 'last active', va[-1][:400] if va else '')
    mem = [int(l.split('","')[-1].replace('.', '').split()[0]) for l in (RT[k] / 'mem.csv').read_text().splitlines() if 'MotorStorm' in l]
    print(k, 'working set KB max', max(mem), 'last', mem[-1])
    print(k, 'timeline', [(json.loads(l)['kind'], json.loads(l)['host_s']) for l in (RT[k] / 'timeline.jsonl').read_text().splitlines() if json.loads(l)['kind'] in ('race_entry', 'controller_stop', 'serious')])


def luma(a):
    return a[..., 0] * .2126 + a[..., 1] * .7152 + a[..., 2] * .0722


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.float32)


def metrics(a):
    y = luma(a)
    h = y.shape[0]
    gx, gy = np.abs(np.diff(y, axis=1))[:-1], np.abs(np.diff(y, axis=0))[:, :-1]
    e = np.maximum(gx, gy)
    lap = y[1:-1, 1:-1] * 4 - y[:-2, 1:-1] - y[2:, 1:-1] - y[1:-1, :-2] - y[1:-1, 2:]
    return dict(black=float((y < 8).mean() * 100), white=float((a.min(axis=2) > 247).mean() * 100), mean=float(y.mean()), lower_third=float(y[2 * h // 3:].mean()),
                edge=float((e > 48).mean() * 100), detail=float(lap.std()))


def small(a):
    y = luma(a)
    h, w = y.shape
    s = y[:h - h % 8, :w - w % 8].reshape(h // 8, 8, w // 8, 8).mean(axis=(1, 3))
    return (s - s.mean()) / (s.std() + 1e-6)


IM = {k: sorted((RT[k] / 'frames').glob('frame_*.bmp')) for k in RT}
A = {k: [load(p) for p in v] for k, v in IM.items()}
M = {k: [metrics(a) for a in v] for k, v in A.items()}
print('| dump | near-black % | clipped white % | mean luma | lower-third luma | edges % | detail |\n|---|---|---|---|---|---|---|')
for k in M:
    for i, m in enumerate(M[k]):
        print(f'| {k} {i} | {m["black"]:.2f} | {m["white"]:.2f} | {m["mean"]:.1f} | {m["lower_third"]:.1f} | {m["edge"]:.2f} | {m["detail"]:.1f} |')
S = {k: [small(a) for a in v] for k, v in A.items()}
C = np.array([[float((x * y).mean()) for y in S['F2']] for x in S['D2']])
print('NCC D2(row) vs F2(col)\n', np.round(C, 2))
pairs = sorted(((C[i, j], i, j) for i in range(C.shape[0]) for j in range(C.shape[1])), reverse=True)
used, kept = set(), []
for c, i, j in pairs:
    if i not in {u[0] for u in used} and j not in {u[1] for u in used}:
        used.add((i, j))
        kept.append((round(c, 3), i, j))
print('greedy pairs (ncc, D2, F2)', kept)
W = 640
for name, rows in (('all', list(range(8))),):
    h = int(W * A['D2'][0].shape[0] / A['D2'][0].shape[1])
    sheet = Image.new('RGB', (W * 2, h * len(kept)))
    d = ImageDraw.Draw(sheet)
    for r, (c, i, j) in enumerate(kept):
        sheet.paste(Image.open(IM['D2'][i]).convert('RGB').resize((W, h)), (0, r * h))
        sheet.paste(Image.open(IM['F2'][j]).convert('RGB').resize((W, h)), (W, r * h))
        d.text((4, r * h + 4), f'D2 {i} / F2 {j} ncc {c}', fill=(255, 255, 0))
    (T / 'img').mkdir(exist_ok=True)
    sheet.save(T / 'img' / 'd2_f2_pairs.png')
print('wrote img/d2_f2_pairs.png')
