"""T169: looks for a solid blue rectangle in dumped frames and RSXI snapshots: 8x8 blocks at least 85 % saturated
blue, joined; reports regions of at least 4 blocks filling their bounding box by at least 85 %.
usage: py -3 blue_scan_t169.py <dir> [<dir> ...]"""
import glob, os, sys
import numpy as np
from PIL import Image

files = 0
hits = []
for root in sys.argv[1:]:
    for f in glob.glob(os.path.join(root, '**', '*.bmp'), recursive=True) + glob.glob(os.path.join(root, '**', '*.png'), recursive=True):
        try:
            a = np.asarray(Image.open(f).convert('RGB')).astype(int)
        except Exception:
            continue
        files += 1
        m = (a[..., 2] > 140) & (a[..., 2] > a[..., 0] * 2) & (a[..., 2] > a[..., 1] * 1.5)
        H, W = m.shape[0] // 8, m.shape[1] // 8
        if not H or not W or m.sum() < 200:
            continue
        g = m[:H * 8, :W * 8].reshape(H, 8, W, 8).mean((1, 3)) >= 0.85
        seen = np.zeros_like(g)
        for y, x in zip(*np.nonzero(g)):
            if seen[y, x]:
                continue
            st, cells = [(y, x)], []
            seen[y, x] = True
            while st:
                b, c = st.pop()
                cells.append((b, c))
                for q, r in ((b + 1, c), (b - 1, c), (b, c + 1), (b, c - 1)):
                    if 0 <= q < H and 0 <= r < W and g[q, r] and not seen[q, r]:
                        seen[q, r] = True
                        st.append((q, r))
            ys, xs = zip(*cells)
            bh, bw = max(ys) - min(ys) + 1, max(xs) - min(xs) + 1
            if len(cells) >= 4 and len(cells) >= 0.85 * bh * bw:
                hits.append((len(cells) * 64, bw * 8, bh * 8, min(xs) * 8, min(ys) * 8, f))
print('images scanned', files, 'candidates', len(hits))
for x in sorted(hits, reverse=True)[:25]:
    print(x)
