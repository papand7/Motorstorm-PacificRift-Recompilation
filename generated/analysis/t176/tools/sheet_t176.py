"""T176: A|B sheets at matched race clocks, and whole-frame numbers. usage: py -3 sheet_t176.py <rtA> <rtB> <out> iA:iB ..."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
ra, rb, out = map(Path, sys.argv[1:4])
for p in sys.argv[4:]:
    i, j = p.split(':')
    A = Image.open(ra / 'frames' / f'frame_{int(i):03}.bmp').convert('RGB'); B = Image.open(rb / 'frames' / f'frame_{int(j):03}.bmp').convert('RGB')
    s = Image.new('RGB', (A.width, A.height * 2)); s.paste(A, (0, 0)); s.paste(B, (0, A.height))
    s.save(out / f'pair_{i}_{j}.png')
    a, b = np.asarray(A, float), np.asarray(B, float)
    print(p, f'mean A {a.mean():.1f} B {b.mean():.1f}, abs diff {np.abs(a - b).mean():.1f}, A black {(a.max(2) < 8).mean():.3f} B black {(b.max(2) < 8).mean():.3f}')
