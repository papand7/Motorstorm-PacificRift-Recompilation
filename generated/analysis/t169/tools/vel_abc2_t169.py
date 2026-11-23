"""T169: dumps of arms A, B, C by HUD race clock: speckle and luma per region, vehicle sheet, debug-layer totals. Private output in img/. Run from this folder (PIL)."""
import json
from pathlib import Path

import numpy as np
from PIL import Image

T = Path(__file__).resolve().parents[1]
RT = {k: next((T / 'ab').glob(f'runtime-{t}-*')) for k, t in (('A', 'VA'), ('B', 'VB'), ('C', 'VC'), ('G', 'VG'))}
CLOCK = {'A': {3: '00.06', 4: '02.39', 5: '04.49', 6: '06.59'}, 'B': {3: '00.06', 4: '02.46', 5: '04.56', 6: '06.66'}, 'C': {4: '01.33', 5: '03.69', 6: '05.79'}, 'G': {4: '01.56', 5: '03.89', 6: '05.99'}}
BOX = {'vehicle': (440, 340, 840, 720), 'tight': (520, 480, 760, 660), 'terrain': (0, 420, 440, 720), 'far': (300, 180, 980, 400)}
op = lambda k, i: np.asarray(Image.open(RT[k] / 'frames' / f'frame_{i:03d}.bmp').convert('RGB'), dtype=np.float32)


def lap(a):
    y = a @ np.array([.2126, .7152, .0722], np.float32)
    return np.abs(y[1:-1, 1:-1] * 4 - y[:-2, 1:-1] - y[2:, 1:-1] - y[1:-1, :-2] - y[1:-1, 2:]), y


print('arm clock | region: median Laplacian, p90 Laplacian, mean luma')
for k, c in CLOCK.items():
    for i, t in c.items():
        a = op(k, i)
        s = []
        for n, b in BOX.items():
            l, y = lap(a[b[1]:b[3], b[0]:b[2]])
            s.append(f'{n} {np.median(l):.1f} {np.percentile(l, 90):.1f} {y.mean():.1f}')
        print(k, t, ' | '.join(s), '| frame luma %.1f' % lap(a)[1].mean())
for name, pairs in (('t2.4-2.5_6.6', [('A', 4), ('B', 4), ('A', 6), ('B', 6)]), ('near', [('A', 4), ('B', 5), ('C', 5), ('C', 4)]), ('corrected', [('A', 4), ('B', 4), ('C', 4), ('G', 4)]), ('corrected2', [('A', 5), ('B', 5), ('C', 5), ('G', 5)])):
    b = BOX['vehicle']
    w, h = b[2] - b[0], b[3] - b[1]
    s = Image.new('RGB', ((w + 4) * len(pairs), h))
    for j, (k, i) in enumerate(pairs):
        s.paste(Image.fromarray(op(k, i)[b[1]:b[3], b[0]:b[2]].astype('uint8')), (j * (w + 4), 0))
    s.save(T / 'img' / f'abc_{name}.png')
for k, r in RT.items():
    d = json.loads((r / 'd3d12_messages.json').read_text())
    print(k, 'd3d12', sorted(((m['severity'], m['id'], m['n']) for m in d['messages']), key=lambda x: -x[2]), 'other', d['other_ods_lines'])
