"""T175: AMD corner frame vs AMD indexed frame, against RTX and WARP. usage: py -3 amd_three_way_t175.py <run set, e.g. px_150> [runs dir]"""
import pathlib, struct, sys, collections
tag = sys.argv[1]
R = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else 'runs')


def load(p):
    b = p.read_bytes()
    off = struct.unpack('<I', b[10:14])[0]
    w, h = struct.unpack('<ii', b[18:26])
    n = struct.unpack('<H', b[28:30])[0] // 8
    return b[off:], w, abs(h), n, (w * n + 3) & ~3


for name in ('frame_000.bmp', 'frame_002.bmp'):
    a, w, h, n, st = load(R / f'{tag}_igp/off/f/{name}')
    i = load(R / f'{tag}_igp/ix/f/{name}')[0]
    r = load(R / f'{tag}/off/f/{name}')[0]
    s = load(R / f'{tag}_warp/off/f/{name}')[0]
    px = lambda b, x, y: b[y * st + x * n:y * st + x * n + n]
    res = collections.Counter()
    rw = am = 0
    pts = []
    for y in range(h):
        if a[y * st:y * st + w * n] == i[y * st:y * st + w * n]:
            pass
        for x in range(w):
            pa, pi, pr, ps = px(a, x, y), px(i, x, y), px(r, x, y), px(s, x, y)
            rw += pr != ps
            am += pa != pr
            if pa != pi:
                pts.append((x, y))
                res['corner=rtx' if pa == pr else ('indexed=rtx' if pi == pr else 'neither=rtx')] += 1
                res['corner=warp' if pa == ps else ('indexed=warp' if pi == ps else 'neither=warp')] += 1
    S = set(pts)
    iso = sum(1 for x, y in pts if not any((x + dx, y + dy) in S for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy))
    print(name, f'{w}x{h}', 'amd corner vs indexed', len(pts), 'isolated', iso, dict(res), 'rtx vs warp', rw, 'amd corner vs rtx', am, 'sample', pts[:6])
