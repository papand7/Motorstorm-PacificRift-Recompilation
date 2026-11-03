"""T141: pixel classes of test_t141_backend's RSXI end-of-frame snapshots (frame 5).
RT_A 0x08000000: inside the middle-half quad 128 if both feedback draws saw the draws before them
(32 -> 64 -> 128), else 64 or 32; outside it the clear 32. RT_D 0x0C000000: Z_A read as A8R8G8B8
(BMP holds R = depth[15:8], G = depth[7:0], B = stencil); far plane outside the triangle.
usage: python fb_backend.py <run_dir>..."""
import sys, os, glob, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't137', 'tools'))
from msaa_backend import load


def snap(run, rt):
    f = glob.glob(os.path.join(run, 'rsxi', 'frames', '*', 'snap*_end_*_rt_%s.bmp' % rt)) or \
        glob.glob(os.path.join(run, 'rsxi', 'frames', '*', 'snap*_rt_%s.bmp' % rt))
    return load(sorted(f)[-1]) if f else None


for run in sys.argv[1:]:
    W, H = 1259, 708
    for l in open(os.path.join(run, 'err.txt'), encoding='utf-8', errors='replace'):
        if l.startswith('[t141] frame 5:'): W, H = (int(v) for v in l.split()[-1].split('x'))
    a, d = snap(run, '08000000'), snap(run, '0C000000')
    name = os.path.basename(run.rstrip('/'))
    if not a: print(name, 'no RT_A snapshot'); continue
    x0, x1, y0, y1 = W // 4 + 1, (3 * W) // 4 - 1, H // 4 + 1, (3 * H) // 4 - 1
    mid = collections.Counter(a[2][y][x] for y in range(y0, y1) for x in range(x0, x1))
    out = collections.Counter(a[2][y][x] for y in range(H) for x in range(W)
                              if not (x0 - 2 <= x < x1 + 2 and y0 - 2 <= y < y1 + 2))
    n = (x1 - x0) * (y1 - y0)
    print('%-9s %dx%d  middle: %d px, %s;  outside: %s' % (name, W, H, n,
          ', '.join('%s x%d' % (k, v) for k, v in mid.most_common(3)), ', '.join('%s x%d' % (k, v) for k, v in out.most_common(2))))
    if d:
        far, near = d[2][5][W - 5], d[2][H - 150][150]
        print('%-9s Z_A as colour: far plane (R,G,B) = %s -> depth[15:0] 0x%02X%02X; depth 0.65 = %s -> 0x%02X%02X'
              % ('', far, far[0], far[1], near, near[0], near[1]))
