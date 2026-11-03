"""T137: compare the RSXI end-of-frame snapshots of test_t137_msaa_backend between arms.

usage: python msaa_backend.py <run_off_dir> <run_on_dir>
RT_A (0x08000000) = the antialias-3 scene as single-sample readers see it (the resolve);
RT_B (0x0A000000) = the guest's own downsample (one bilinear tap per sample pair).
Pixel classes: white (255,255,255), red (255,0,0), black (clear), mixed (anything else).
"""
import sys, os, glob, struct


def load(path):
    b = open(path, 'rb').read()
    off, = struct.unpack_from('<I', b, 10); w, h = struct.unpack_from('<ii', b, 18)
    row = (w * 3 + 3) & ~3
    px = []
    for y in range(abs(h)):
        r = off + (abs(h) - 1 - y) * row if h > 0 else off + y * row
        px.append([(b[r + 3 * x + 2], b[r + 3 * x + 1], b[r + 3 * x]) for x in range(w)])
    return w, abs(h), px


def snap(run, rt):
    f = glob.glob(os.path.join(run, 'rsxi', 'frames', '*', 'snap*_rt_%s.bmp' % rt))
    return load(f[0]) if f else None


def classes(img, W, H):
    c = {'white': 0, 'red': 0, 'black': 0, 'mixed': 0}
    for y in range(H):
        for x in range(W):
            p = img[2][y][x]
            k = 'white' if p == (255, 255, 255) else 'red' if p == (255, 0, 0) else 'black' if p == (0, 0, 0) else 'mixed'
            c[k] += 1
    return c


def main(off, on):
    vp = None
    for l in open(os.path.join(on, 'err.txt'), encoding='utf-8', errors='replace'):
        if l.startswith('[t137] frame 5:'): vp = tuple(int(v) for v in l.split()[-1].split('x'))
    W, H = vp or (1259, 708)
    print('frame 5 viewport %dx%d' % (W, H))
    res = {}
    for arm, run in (('off', off), ('on', on)):
        for rt in ('08000000', '0A000000'):
            s = snap(run, rt)
            if not s: print(arm, rt, 'no snapshot'); continue
            res[(arm, rt)] = s
            print('%-3s RT_%s %dx%d inside viewport: %s' % (arm, rt, s[0], s[1], classes(s, W, H)))
    if ('on', '08000000') in res and ('on', '0A000000') in res:
        a, b = res[('on', '08000000')][2], res[('on', '0A000000')][2]
        diff = max(max(abs(a[y][x][k] - b[y][x][k]) for k in range(3)) for y in range(H) for x in range(W))
        print('on: max |guest downsample - resolve| over the viewport = %d' % diff)
    if ('off', '0A000000') in res and ('on', '0A000000') in res:
        a, b = res[('off', '0A000000')][2], res[('on', '0A000000')][2]
        same = sum(1 for y in range(H) for x in range(W) if a[y][x] == b[y][x])
        print('off vs on RT_B: %d of %d viewport pixels identical' % (same, W * H))
        edge = [(x, y) for y in range(H) for x in range(W) if a[y][x] != b[y][x]]
        bad = [p for p in edge if b[p[1]][p[0]] in ((255, 255, 255), (255, 0, 0), (0, 0, 0))]
        print('pixels that differ: %d; of those, still pure in the on arm: %d' % (len(edge), len(bad)))
        if edge: print('sample differing pixels (x, y, off, on):', [(x, y, a[y][x], b[y][x]) for x, y in edge[:6]])


def zeta(off, on, W, H):
    a, b = snap(off, '0C000000'), snap(on, '0C000000')
    if not a or not b: print('zeta image: no snapshot'); return
    a, b = a[2], b[2]
    same = sum(1 for y in range(H) for x in range(W) if a[y][x] == b[y][x])
    print('zeta read as A8R8G8B8 (RT_D, NEAREST): %d of %d viewport pixels identical off vs on' % (same, W * H))
    print('  values at (300, 300): off %s on %s; at (5, 5): off %s on %s' % (a[300][300], b[300][300], a[5][5], b[5][5]))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
    zeta(sys.argv[1], sys.argv[2], 1260, 708)
