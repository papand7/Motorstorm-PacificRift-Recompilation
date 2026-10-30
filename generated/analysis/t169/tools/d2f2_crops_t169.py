"""T169: full-resolution crops of the D2/F2 dumps paired by the HUD race clock, and a D1/D2 sheet. Private output in img/. Run from this folder (PIL)."""
from pathlib import Path
from PIL import Image

T = Path(__file__).resolve().parents[1]
RT = {k: next((T / 'ab').glob(f'runtime-{k}-*')) / 'frames' for k in ('D1', 'D2', 'F2')}
op = lambda k, i: Image.open(RT[k] / f'frame_{i:03d}.bmp').convert('RGB')
BOX = {'vehicle': (440, 340, 840, 720), 'terrain': (0, 420, 440, 720), 'far': (300, 180, 980, 400)}
for pair in (7, 4):
    for name, b in BOX.items():
        w, h = b[2] - b[0], b[3] - b[1]
        s = Image.new('RGB', (w * 2 + 4, h))
        s.paste(op('D2', pair).crop(b), (0, 0))
        s.paste(op('F2', pair).crop(b), (w + 4, 0))
        s.save(T / 'img' / f'd2f2_{pair}_{name}.png')
d1 = sorted(RT['D1'].glob('*.bmp'))
print('D1 dumps', len(d1))
n = min(len(d1), 8)
s = Image.new('RGB', (1280, 360 * ((n + 1) // 2)))
for i, p in enumerate(d1[:8]):
    s.paste(Image.open(p).convert('RGB').resize((640, 360)), (640 * (i % 2), 360 * (i // 2)))
s.save(T / 'img' / 'd1_sheet.png')
