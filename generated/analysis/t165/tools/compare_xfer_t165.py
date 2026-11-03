"""T165: measured comparison of two frame dumps of the same game moment (arm B against arm X), 24-bit BMP.
Regions are hand-placed on the matched player-quad frame (frame_001 of runs B3 and X1).
usage: py -3 compare_xfer_t165.py <B.bmp> <X.bmp>"""
import struct, sys

REGIONS = {'front tyre': (700, 530, 800, 700), 'left tyre': (370, 490, 490, 660), 'quad frame+fairing': (480, 310, 720, 600),
           'rider jacket+legs': (640, 230, 770, 500), 'helmet': (680, 165, 735, 225), 'sand left': (40, 430, 330, 640),
           'sand right': (900, 480, 1250, 700), 'cliff shade': (100, 120, 400, 280), 'lit bank': (800, 300, 1200, 400),
           'palm': (830, 10, 1000, 100), 'whole frame': (0, 0, 1280, 720)}


def read(p):
    b = open(p, 'rb').read()
    off = struct.unpack_from('<I', b, 10)[0]
    w, h = struct.unpack_from('<ii', b, 18)
    bpp = struct.unpack_from('<H', b, 28)[0] // 8
    stride = (w * bpp + 3) & ~3
    flip = h > 0
    h = abs(h)

    def px(x, y):
        o = off + (h - 1 - y if flip else y) * stride + x * bpp
        return b[o + 2], b[o + 1], b[o]
    return w, h, px


def luma(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def stats(px, r):
    n = blk = clip = 0
    s = 0.0
    for y in range(r[1], r[3]):
        for x in range(r[0], r[2]):
            c = px(x, y)
            l = luma(c)
            s += l
            n += 1
            blk += max(c) <= 16
            clip += min(c) >= 250
    return s / n, 100.0 * blk / n, 100.0 * clip / n


w, h, a = read(sys.argv[1])
_, _, b = read(sys.argv[2])
print('| Region | B luma | X luma | B near-black % | X near-black % | B clipped % | X clipped % |')
print('|---|---|---|---|---|---|---|')
for name, r in REGIONS.items():
    p, q = stats(a, r), stats(b, r)
    print(f'| {name} | {p[0]:.1f} | {q[0]:.1f} | {p[1]:.1f} | {q[1]:.1f} | {p[2]:.1f} | {q[2]:.1f} |')
bands = [(0, 8), (8, 16), (16, 32), (32, 64), (64, 128), (128, 192), (192, 250), (250, 256)]
hist = {x: [] for x in bands}
for y in range(0, h, 2):
    for x in range(0, w, 2):
        lb = luma(a(x, y))
        for k in bands:
            if k[0] <= lb < k[1]:
                hist[k].append(luma(b(x, y)))
                break
print('\n| B luma band | pixels | median X luma |\n|---|---|---|')
for k in bands:
    v = sorted(hist[k])
    if v:
        print(f'| {k[0]}-{k[1]} | {len(v) * 4} | {v[len(v) // 2]:.1f} |')
