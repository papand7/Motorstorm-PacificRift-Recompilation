"""T182: pixel distance between arms: changed pixels, largest and mean channel delta. usage: amd_diff_t182.py <a dir> <b dir> ... (pairs)"""
import struct, sys
from pathlib import Path
def load(p):
    b = p.read_bytes(); o = struct.unpack('<I', b[10:14])[0]; return b[o:]
A = sys.argv[1:]
for a, b in zip(A[::2], A[1::2]):
    x, y = load(Path('runs') / a / 'f' / 'frame_002.bmp'), load(Path('runs') / b / 'f' / 'frame_002.bmp')
    n = 0; mx = 0; tot = 0
    for i in range(0, min(len(x), len(y)), 4):
        d = max(abs(x[i] - y[i]), abs(x[i + 1] - y[i + 1]), abs(x[i + 2] - y[i + 2]))
        if d: n += 1; mx = max(mx, d); tot += d
    print(f'{a} vs {b}: changed {n} of {len(x)//4}, max {mx}, mean {tot/max(n,1):.1f}')
