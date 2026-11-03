"""T172: fit after = before*(1-a) + c inside each patch of TA f005564 and show them enlarged. Run from t169/tools (PIL). usage: py -3 patchfit_t172.py"""
import glob
from pathlib import Path
import numpy as np
from PIL import Image

OUT = Path('../../t172/img')
d = Path(glob.glob('../../t171/ab/runtime-TA-*/rsxi/frames/*')[0])
A = np.asarray(Image.open(next(d.glob('snap04*'))).convert('RGB'), np.float32)
B = np.asarray(Image.open(next(d.glob('snap05*'))).convert('RGB'), np.float32)
for name, (x0, y0, x1, y1) in {'patch1': (725, 287, 751, 308), 'patch2': (586, 309, 609, 329), 'ground_left': (40, 500, 400, 700), 'ground_mid': (480, 640, 800, 700), 'ground_right': (900, 400, 1200, 700), 'sky_band': (420, 180, 620, 215)}.items():
    a, b = A[y0:y1 + 1, x0:x1 + 1].reshape(-1, 3), B[y0:y1 + 1, x0:x1 + 1].reshape(-1, 3)
    out = []
    for c in range(3):
        k, m = np.polyfit(a[:, c], b[:, c], 1)
        out.append((round(float(k), 3), round(float(m), 1), round(float(np.corrcoef(a[:, c], b[:, c])[0, 1]), 3)))
    print(name, 'mean before', np.round(a.mean(0), 1), 'after', np.round(b.mean(0), 1), 'std after', np.round(b.std(0), 1), 'fit (k,m,r) per channel', out)
o = Image.new('RGB', (1210, 410), (255, 0, 255))
for i, im in enumerate((A, B)):
    c = Image.fromarray(np.uint8(im)).crop((570, 270, 770, 340)).resize((600, 210), Image.NEAREST)
    o.paste(c, (i * 610, 0))
D = np.abs(B - A).max(2)
o.paste(Image.fromarray(np.uint8(np.clip(D, 0, 255))).crop((570, 270, 770, 340)).resize((600, 190), Image.NEAREST).convert('RGB'), (0, 215))
o.save(OUT / 'patch_zoom.png')
