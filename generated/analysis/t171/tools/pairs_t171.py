"""T171: matched-clock crops, A over B, and difference numbers. Run from t169/tools (PIL). usage: py -3 pairs_t171.py"""
from pathlib import Path
import numpy as np
from PIL import Image

T = Path('../../t171').resolve()
A = next((T / 'ab').glob('runtime-TA-*')) / 'frames'
B = next((T / 'ab').glob('runtime-TB-*')) / 'frames'
for n, (a, b, cl) in enumerate([(7, 6, '0.7'), (8, 7, '1.7'), (9, 8, '3.0'), (10, 9, '4.1')]):
    x = Image.open(A / f'frame_{a:03d}.bmp').convert('RGB')
    y = Image.open(B / f'frame_{b:03d}.bmp').convert('RGB')
    o = Image.new('RGB', (1280, 860), (255, 0, 255))
    o.paste(x.crop((0, 290, 1280, 715)), (0, 0))
    o.paste(y.crop((0, 290, 1280, 715)), (0, 435))
    o.save(T / 'img' / f'pair_{n}_clock{cl}.png')
    d = np.abs(np.asarray(x, np.int16) - np.asarray(y, np.int16)).mean(2)
    print(cl, 'mean diff', round(float(d.mean()), 2), 'lower half', round(float(d[360:].mean()), 2))
