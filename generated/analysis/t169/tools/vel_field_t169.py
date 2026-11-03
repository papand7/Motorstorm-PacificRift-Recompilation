"""T169: reads the x half out of a captured velocity target (BMP keeps R=x_lo, G=x_hi, B=y_lo; alpha is lost) and reports its range and smoothness.
Also the before and after of the composite. Private images in img/. Run from this folder (PIL). usage: py -3 vel_field_t169.py <runtime tag>"""
import glob, sys
from pathlib import Path
import numpy as np
from PIL import Image

T = Path(__file__).resolve().parents[1]
rt = next((T / 'ab').glob(f'runtime-{sys.argv[1]}-*'))
for p in sorted(glob.glob(str(rt / 'rsxi/frames/*/snap*rt_01650000*'))):
    a = np.asarray(Image.open(p).convert('RGB'), dtype=np.uint16)
    x = np.frombuffer((a[..., 0] | (a[..., 1] << 8)).astype('<u2').tobytes(), dtype='<f2').reshape(a.shape[:2]).astype(np.float32)
    f = np.isfinite(x)
    v = x[f]
    nz = np.any(a != 0, axis=2)
    dx = np.abs(np.diff(np.where(f, x, 0), axis=1))
    swap = np.frombuffer((a[..., 1] | (a[..., 0] << 8)).astype('<u2').tobytes(), dtype='<f2').reshape(a.shape[:2]).astype(np.float32)
    print(Path(p).name, a.shape[1], a.shape[0], 'nonzero %.1f%% finite %.2f%%' % (nz.mean() * 100, f.mean() * 100),
          'x p1 %.5f p50 %.5f p99 %.5f max|x| %.3f' % (np.percentile(v, 1), np.percentile(v, 50), np.percentile(v, 99), np.abs(v).max()),
          'neighbour diff med %.6f p99 %.5f' % (np.median(dx), np.percentile(dx, 99)),
          '| swapped bytes max|x| %.1f p99 %.3f' % (np.nanmax(np.abs(swap[np.isfinite(swap)])), np.percentile(np.abs(swap[np.isfinite(swap)]), 99)))
    im = np.clip(np.nan_to_num(x) * 40 + .5, 0, 1)
    Image.fromarray((im * 255).astype('uint8')).save(T / 'img' / f'velx_{sys.argv[1]}_{Path(p).stem[:6]}.png')
