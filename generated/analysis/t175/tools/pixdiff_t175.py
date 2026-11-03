"""T175: differing pixels between two frame directories. usage: py -3 pixdiff_t175.py <dir a> <dir b>"""
import pathlib, struct, sys
A, B = map(pathlib.Path, sys.argv[1:3])


def load(p):
    b = p.read_bytes()
    off = struct.unpack('<I', b[10:14])[0]
    w, h = struct.unpack('<ii', b[18:26])
    n = struct.unpack('<H', b[28:30])[0] // 8
    return b[off:], w, abs(h), n, (w * n + 3) & ~3


tot = 0
for f in sorted(A.glob('*.bmp'))[:3]:
    a, w, h, n, st = load(f)
    c = load(B / f.name)[0]
    d = big = 0
    for y in range(h):
        ra, rb = a[y * st:y * st + w * n], c[y * st:y * st + w * n]
        if ra == rb:
            continue
        for x in range(w):
            pa, pb = ra[x * n:x * n + n], rb[x * n:x * n + n]
            if pa != pb:
                d += 1
                big += max(abs(i - j) for i, j in zip(pa, pb)) > 8
    print(f'{f.name} differ {d} ({100 * d / (w * h):.3f}%), of which delta>8: {big}')
    tot += d
print('total', tot)
