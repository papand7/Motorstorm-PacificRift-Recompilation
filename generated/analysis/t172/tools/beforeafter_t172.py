"""T172: the patch region across the pass snapshots of TA f005564, and the depth-state arm's final frames. Run from t169/tools (PIL). usage: py -3 beforeafter_t172.py"""
import glob
from pathlib import Path
import numpy as np
from PIL import Image

OUT = Path('../../t172/img')
d = Path(glob.glob('../../t171/ab/runtime-TA-*/rsxi/frames/*')[0])
names = ['snap01', 'snap04', 'snap05', 'snap20', 'snap21']
box = (400, 150, 900, 350)
o = Image.new('RGB', (1000, 3 * 410), (255, 0, 255))
for i, n in enumerate(names):
    im = Image.open(next(d.glob(n + '*'))).convert('RGB').crop(box)
    o.paste(im.resize((500, 200)), ((i % 2) * 500, (i // 2) * 410))
    print(i, next(d.glob(n + '*')).name)
o.paste(Image.open(next(d.glob('snap03*'))).convert('RGB').resize((500, 281)), (500, 820))
o.save(OUT / 'patch_passes.png')
a = np.asarray(Image.open(next(d.glob('snap04*'))).convert('RGB'), np.int16)
b = np.asarray(Image.open(next(d.glob('snap05*'))).convert('RGB'), np.int16)
D = (b - a).sum(2)
# connected strong-darkening blobs: the patches
m = np.abs(b - a).max(2) > 40
from collections import deque
seen = np.zeros(m.shape, bool)
blobs = []
for y, x in zip(*np.nonzero(m)):
    if seen[y, x]:
        continue
    q, pts = deque([(y, x)]), []
    seen[y, x] = True
    while q:
        cy, cx = q.popleft(); pts.append((cy, cx))
        for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
            if 0 <= ny < 720 and 0 <= nx < 1280 and m[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True; q.append((ny, nx))
    if len(pts) >= 60:
        p = np.array(pts)
        y0, x0, y1, x1 = p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()
        blobs.append((len(pts), int(x0), int(y0), int(x1), int(y1), round(len(pts) / ((x1 - x0 + 1) * (y1 - y0 + 1)), 2), [int(v) for v in (b - a)[p[:, 0], p[:, 1]].mean(0)]))
print('blobs n,x0,y0,x1,y1,fill,meanDelta', sorted(blobs, reverse=True)[:12])
