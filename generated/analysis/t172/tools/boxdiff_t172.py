"""T172: what the box draws (fp 0x022C20C1) change, between the 00750000 snapshots around them. Run from t169/tools (PIL).
usage: py -3 boxdiff_t172.py"""
from pathlib import Path
import numpy as np
from PIL import Image

A = Path('../../').resolve()
OUT = A / 't172' / 'img'
CASES = [('TA_depth0', 't171/ab/runtime-TA-*/rsxi/frames/*', 'snap04_', 'snap05_'),
         ('D1', 't169/ab/runtime-D1-*/rsxi/frames/*', 'snap05_', 'snap06_')]
for tag, pat, a, b in CASES:
    d = next(A.glob(pat))
    x = Image.open(next(d.glob(a + '*'))).convert('RGB')
    y = Image.open(next(d.glob(b + '*'))).convert('RGB')
    X, Y = np.asarray(x, np.int16), np.asarray(y, np.int16)
    D = np.abs(Y - X).max(2)
    m = D > 3
    print(tag, next(d.glob(a + '*')).name, '->', next(d.glob(b + '*')).name, 'changed', int(m.sum()), 'frac', round(float(m.mean()), 4))
    if m.any():
        ys, xs = np.nonzero(m)
        print('  bbox', xs.min(), ys.min(), xs.max(), ys.max(), 'signed mean', np.round((Y - X)[m].mean(0), 1), 'above horizon-ish y<240:', int((ys < 240).sum()))
    o = Image.new('RGB', (1280, 720 * 2 + 8), (255, 0, 255))
    o.paste(y, (0, 0))
    o.paste(Image.fromarray(np.uint8(np.clip(D[..., None].repeat(3, 2) * 6, 0, 255))), (0, 728))
    o.save(OUT / f'boxdiff_{tag}.png')
