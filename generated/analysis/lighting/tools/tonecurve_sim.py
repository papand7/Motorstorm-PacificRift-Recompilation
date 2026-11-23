r"""Applies the scene-pass tone curve (sRGB decode, exposure, ACES fit normalised by the white point, mix, sRGB encode) to
real frames offline and prints the luminance change, so the default exposure can be chosen on data, not by eye.
usage: py -3 tonecurve_sim.py <dir> [step]    (frames of a run WITHOUT tone mapping, e.g. lt3)"""
import sys, glob
import numpy as np
from PIL import Image

def s2l(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def l2s(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 1e-9), 1 / 2.4) - 0.055)
def aces(x): return np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)
def tm(c, e, wp, k):
    l = s2l(c); t = aces(l * e) / aces(np.full(1, wp * e))[0]
    return np.clip(l2s(np.clip(l + k * (t - l), 0, 1)), 0, 1)

fs = sorted(glob.glob(sys.argv[1] + '/shot_*.png') + glob.glob(sys.argv[1] + '/shot_*.bmp'))
fs = fs[::int(sys.argv[2]) if len(sys.argv) > 2 else 6]
ims = []
for f in fs:
    a = np.asarray(Image.open(f).convert('RGB').resize((480, 270)), dtype=np.float32) / 255.0
    ims.append(a[int(270 * 0.12):int(270 * 0.75)])
def stats(v):
    y = 0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2]
    return y.mean() * 255, np.percentile(y, 5) * 255, np.percentile(y, 95) * 255, (v.max(axis=2) >= 250 / 255).mean() * 100
base = np.mean([stats(a) for a in ims], axis=0)
print(f'{len(ims)} frames of {sys.argv[1]}; input: mean {base[0]:.1f} p5 {base[1]:.1f} p95 {base[2]:.1f} clipped {base[3]:.2f}%')
for e in (1.0, 0.5):
    for wp in (1.0, 1.2):
        s = np.mean([stats(tm(a, e, wp, 1.0)) for a in ims], axis=0)
        print(f'exposure {e:.2f} white {wp:.1f}: mean {s[0]:.1f} ({s[0]-base[0]:+.1f}) p5 {s[1]:.1f} p95 {s[2]:.1f} clipped {s[3]:.2f}%')
