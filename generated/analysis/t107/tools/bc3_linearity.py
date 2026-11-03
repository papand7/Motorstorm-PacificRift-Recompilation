"""T107: is the presented loading artwork exactly `BC3 decode x gain`, with no
transfer function anywhere between the texture and the dump?

A DXT5 colour block decodes to at most 4 colours: c0, c1, (2c0+c1)/3 and
(c0+2c1)/3. A pure multiplicative gain followed by 8-bit rounding keeps the
4 colours collinear and evenly spaced (within rounding). Any sRGB decode,
encode or double conversion bends the spacing. For each aligned 4x4 block
with no clipped (255) or near-black channel this reports how many distinct
colours it has, and for 3-4-colour blocks the worst deviation of the inner
colours from even spacing on the measured path. It also predicts, for the
same blocks, the deviation a srgb_encode(gain * srgb_decode(x)) path would
show, to prove the test can tell the two apart.

Usage: bc3_linearity.py <bmp> <gain>"""
import sys
sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0] + '/../../t103/tools')
from bb_stats import load_bmp  # noqa: E402


def s2l(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def l2s(v):
    v = min(max(v, 0.0), 1.0)
    return 255.0 * (v * 12.92 if v < 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)


def spacing_dev(cols):
    """cols: 3 or 4 RGB tuples. Order them along the axis of the farthest
    pair, then compare the inner ones with the 1/3, 2/3 points."""
    best = None
    for i in range(len(cols)):
        for j in range(len(cols)):
            d = sum((cols[i][k] - cols[j][k]) ** 2 for k in range(3))
            if best is None or d > best[0]:
                best = (d, i, j)
    _, i, j = best
    a, b = cols[i], cols[j]
    if best[0] < 30 ** 2:        # too flat to say anything about spacing
        return None
    inner = [c for n, c in enumerate(cols) if n not in (i, j)]
    worst = 0.0
    for c in inner:
        devs = []
        for t in (1 / 3, 2 / 3):
            devs.append(max(abs(c[k] - (a[k] + (b[k] - a[k]) * t)) for k in range(3)))
        worst = max(worst, min(devs))
    return worst


def main():
    p, gain = sys.argv[1], float(sys.argv[2])
    w, h, img = load_bmp(p)
    hist = {}
    meas, model = [], []
    for by in range(0, h - 3, 4):
        for bx in range(0, w - 3, 4):
            px = [img[by + y][bx + x] for y in range(4) for x in range(4)]
            if any(max(c) >= 255 or min(c) < 8 for c in px):
                continue
            cols = sorted(set(px))
            hist[min(len(cols), 9)] = hist.get(min(len(cols), 9), 0) + 1
            if len(cols) not in (3, 4):
                continue
            d = spacing_dev(cols)
            if d is None:
                continue
            meas.append(d)
            # same block through a gamma-correct pipeline: texels x = out/gain
            tex = [tuple(v / gain for v in c) for c in cols]
            gam = [tuple(l2s(gain * s2l(v)) for v in c) for c in tex]
            if all(max(c) < 255 for c in gam):
                dm = spacing_dev(gam)
                if dm is not None:
                    model.append(dm)
    tot = sum(hist.values())
    print(f"{p}: gain {gain}, unclipped blocks {tot}")
    print("  distinct colours per block: " +
          " ".join(f"{k}{'+' if k == 9 else ''}:{v} ({v / tot:.3f})" for k, v in sorted(hist.items())))
    for name, v in (("measured", meas), ("gamma model", model)):
        v.sort()
        if not v:
            print(f"  {name}: no 3-4 colour blocks"); continue
        q = lambda f: v[min(len(v) - 1, int(f * len(v)))]
        within = sum(1 for x in v if x <= 1.5) / len(v)
        print(f"  {name}: n={len(v)} spacing dev p50 {q(.5):.2f} p90 {q(.9):.2f} "
              f"p99 {q(.99):.2f}; share <= 1.5 LSB {within:.3f}")


main()
