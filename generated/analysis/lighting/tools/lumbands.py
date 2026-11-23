r"""Mean luminance of the sky band (top 35 %), the middle band and the ground band (bottom half, HUD columns cut) per
shot set. usage: py -3 lumbands.py <dir>..."""
import sys, glob
import numpy as np
from PIL import Image
for d in sys.argv[1:]:
    fs = sorted(glob.glob(d + '/shot_*.png') + glob.glob(d + '/shot_*.bmp'))
    acc = []
    for f in fs:
        a = np.asarray(Image.open(f).convert('RGB').resize((480, 270)), dtype=np.float32)
        y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
        acc.append([y[:95].mean(), y[95:150].mean(), y[150:230, 20:200].mean(), (y[150:230, 20:200] < 70).mean() * 100, y[150:230, 20:200].std()])
    m = np.mean(acc, axis=0)
    print(f'{d}: {len(fs)} shots  sky {m[0]:.1f}  mid {m[1]:.1f}  ground-left {m[2]:.1f} (dark<70 {m[3]:.1f}%  std {m[4]:.1f})')
