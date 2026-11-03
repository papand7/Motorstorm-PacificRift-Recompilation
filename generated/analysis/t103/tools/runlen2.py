"""T103: point-sampled magnification test. Counts exact horizontal runs of
length 2 (a != b == c != d) in unclipped, non-black pixels, and reports their
share by column phase. A 1:1 texel mapping gives a low, phase-flat share; a
point-sampled magnification by s gives a high share with period ~s."""
import sys
sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0])
from bb_stats import load_bmp  # noqa: E402  (bb_stats has no side effects without argv)

for p in [a for a in sys.argv[1:] if a != "--rows"]:
    w, h, img = load_bmp(p)
    if '--rows' in sys.argv:   # same test on the transposed image
        img = [list(c) for c in zip(*img)]; w, h = h, w
    run2 = textured = 0
    by_col = [0] * w
    for row in img:
        for x in range(1, w - 2):
            a, b, c, d = row[x - 1], row[x], row[x + 1], row[x + 2]
            if max(b) == 255 or max(b) < 8:
                continue
            textured += 1
            if a != b and b == c and c != d:
                run2 += 1; by_col[x] += 1
    print(f"{p}: run2 share {run2/max(1,textured):.4f} of {textured} unclipped px")
    for per in (2, 3, 4, 5):
        ph = [sum(by_col[i::per]) for i in range(per)]
        tot = max(1, sum(ph))
        print(f"  period {per}: " + " ".join(f"{v/tot:.3f}" for v in ph))
