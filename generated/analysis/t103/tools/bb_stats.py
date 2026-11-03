"""T103: luminance, clipping and point-sampling-duplication stats of a BMP
backbuffer dump (pure Python, no numpy). Usage: bb_stats.py <bmp>..."""
import sys, struct


def load_bmp(p):
    d = open(p, 'rb').read()
    off, = struct.unpack_from('<I', d, 10)
    w, h, _, bpp = struct.unpack_from('<iiHH', d, 18)
    bb = bpp // 8
    row = (w * bb + 3) & ~3
    rows = []
    for y in range(abs(h)):
        r = d[off + y * row: off + y * row + w * bb]
        rows.append([(r[x * bb + 2], r[x * bb + 1], r[x * bb]) for x in range(w)])
    if h > 0:
        rows.reverse()
    return w, abs(h), rows


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q / 100 * len(v)))] if v else 0


for p in (sys.argv[1:] if __name__ == '__main__' else []):
    w, h, img = load_bmp(p)
    luma, clip, sums = [], 0, [0, 0, 0]
    eqc = nc = eqr = nr = 0
    grad = []
    for y in range(h):
        row = img[y]
        for x in range(w):
            c = row[x]
            sums[0] += c[0]; sums[1] += c[1]; sums[2] += c[2]
            l = lum(c)
            luma.append(l)
            clip += max(c) == 255
            if l <= 4:
                continue
            if x + 1 < w and lum(row[x + 1]) > 4:
                nc += 1; eqc += row[x + 1] == c
                grad.append(abs(l - lum(row[x + 1])))
            if y + 1 < h and lum(img[y + 1][x]) > 4:
                nr += 1; eqr += img[y + 1][x] == c
    N = w * h
    print(f"{p}\n  size {w}x{h}  mean RGB {sums[0]/N:.1f}/{sums[1]/N:.1f}/{sums[2]/N:.1f}"
          f"  luma p50/p95/p99 {pct(luma,50):.0f}/{pct(luma,95):.0f}/{pct(luma,99):.0f}"
          f"  clipped {clip/N:.3f}\n  equal-neighbour cols {eqc/max(1,nc):.3f} rows {eqr/max(1,nr):.3f}"
          f"  mean |dY/dx| {sum(grad)/max(1,len(grad)):.2f}  p99 {pct(grad,99):.0f}")
