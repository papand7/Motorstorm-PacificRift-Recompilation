"""T107: transfer-function check across two dumps of the same static artwork
at different guest fade gains g1, g2 (1 - c59.w). On a purely multiplicative
host path every unclipped channel value v2 = v1 * g2/g1, whatever v1. A
gamma-correct path (sRGB decode, gain in linear, sRGB encode) gives
v2 = l2s(g2/g1 * s2l(v1)): a ratio that depends on v1. Pixels clipped in
either frame and the animated emblem (pixels that are not a pure ratio
outlier-free) are excluded by the median per bin.
Usage: gain_ratio.py <bmp1> <g1> <bmp2> <g2>"""
import os, sys
_here = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_here, os.path.join(_here, '..', '..', 't103', 'tools')]
from bb_stats import load_bmp  # noqa: E402
from bc3_lib import s2l, l2s  # noqa: E402

p1, g1, p2, g2 = sys.argv[1], float(sys.argv[2]), sys.argv[3], float(sys.argv[4])
_, _, a = load_bmp(p1)
_, _, b = load_bmp(p2)
r = g2 / g1
bins = {}
for ra, rb in zip(a, b):
    for ca, cb in zip(ra, rb):
        for va, vb in zip(ca, cb):
            if 8 <= va and vb < 255 and va * r < 250:
                bins.setdefault(va // 16, []).append(vb / va)
print(f"expected linear ratio g2/g1 = {r:.4f}")
print(" v1 bin   n       median   linear   gamma-model")
for k in sorted(bins):
    v = sorted(bins[k]); m = v[len(v) // 2]; c = k * 16 + 8
    gm = l2s(r * s2l(c)) / c
    print(f" {k*16:3d}-{k*16+15:3d} {len(v):7d}  {m:.4f}   {r:.4f}   {gm:.4f}")
