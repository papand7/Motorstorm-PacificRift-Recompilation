"""T171: horizon zooms at matched clocks, plus the mirror check on arm A's capture. Run from t169/tools (PIL). usage: py -3 zoom_t171.py"""
from pathlib import Path
import numpy as np
from PIL import Image

T = Path('../../t171').resolve()
RA = next((T / 'ab').glob('runtime-TA-*'))
RB = next((T / 'ab').glob('runtime-TB-*'))
op = lambda r, n: Image.open(r / 'frames' / f'frame_{n:03d}.bmp').convert('RGB')
box = (480, 215, 1280, 385)
o = Image.new('RGB', (1600, 1050), (255, 0, 255))
for row, (a, b) in enumerate([(7, 6), (9, 8), ]):
    o.paste(op(RA, a).crop(box).resize((1600, 340 // 1 // 1 * 1)).resize((800, 255)), (0, row * 525))
    o.paste(op(RB, b).crop(box).resize((800, 255)), (0, row * 525 + 262))
    o.paste(op(RA, a).crop((0, 260, 800, 515)), (800, row * 525))
    o.paste(op(RB, b).crop((0, 260, 800, 515)), (800, row * 525 + 262))
o.save(T / 'img' / 'zoom_horizon.png')

fr = next((RA / 'rsxi' / 'frames').iterdir())
def L(n):
    return np.asarray(Image.open(next(fr.glob(f'snap{n:02d}_*.bmp'))).convert('L'), np.float32)
b, a = L(1), L(4)   # 00750000 at ops 1798 and 1887; tracks are 1876-1887
ch = np.abs(a - b) > 8
print('changed px', int(ch.sum()), 'mean before', round(float(b[ch].mean()), 1), 'after', round(float(a[ch].mean()), 1))
H = 716
ys, xs = np.nonzero(ch)
ok = ys < H
ys, xs = ys[ok], xs[ok]
mir = b[np.clip(H - 1 - ys, 0, 719), xs]
print('corr after vs mirrored', round(float(np.corrcoef(a[ys, xs], mir)[0, 1]), 3), 'vs own pixel', round(float(np.corrcoef(a[ys, xs], b[ys, xs])[0, 1]), 3))
Image.fromarray(np.uint8(np.where(ch[..., None], np.asarray(Image.open(next(fr.glob('snap04_*.bmp'))).convert('RGB')), np.asarray(Image.open(next(fr.glob('snap04_*.bmp'))).convert('RGB')) // 3))).save(T / 'img' / 'A_capture_track_mask.png')
print('capture end frame', next(fr.glob('snap21_*.bmp')).name)
Image.open(next(fr.glob('snap21_*.bmp'))).convert('RGB').save(T / 'img' / 'A_capture_end.png')
