r"""Mean luminance (Rec.709 on display-encoded values, 0-255) and clipped pixel % (any channel >= 250, and luma <= 5)
per shot, over the region without the HUD (top 12 % and the bottom 25 % left out). usage: py -3 lumstat.py <dir>..."""
import sys, pathlib
import numpy as np
from PIL import Image
for d in sys.argv[1:]:
    rows = []
    for f in sorted(pathlib.Path(d).glob('shot_*.*')):
        if f.suffix not in ('.png', '.bmp') or f.stat().st_size < 1000: continue
        try:
            im = np.asarray(Image.open(f).convert('RGB'), dtype=np.float32)
        except OSError:
            continue
        h = im.shape[0]
        a = im[int(h * 0.12):int(h * 0.75)]
        y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
        sky = (a[..., 2] > a[..., 0] * 1.15) & (y > 120)           # blue sky pixels (rough)
        rows.append((f.stem[-6:], float(y.mean()), float((a.max(axis=2) >= 250).mean() * 100), float((y <= 5).mean() * 100),
                     float(np.percentile(y, 5)), float(np.percentile(y, 95)), float(y[~sky].mean()) if (~sky).any() else 0.0))
    if not rows:
        print(d, 'no shots'); continue
    arr = np.array([r[1:] for r in rows])
    print(f'{d}: {len(rows)} shots  mean {arr[:,0].mean():.1f}  clipped {arr[:,1].mean():.2f}%  black {arr[:,2].mean():.2f}%  p5 {arr[:,3].mean():.1f}  p95 {arr[:,4].mean():.1f}  mean-no-sky {arr[:,5].mean():.1f}')
    if '-v' in sys.argv:
        for r in rows: print('   ', r[0], ' '.join(f'{x:.1f}' for x in r[1:]))
