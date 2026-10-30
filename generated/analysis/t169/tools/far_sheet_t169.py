"""T169: same-clock crops of the vehicle and far band, A C G rows. Private. Run from this folder (PIL)."""
from pathlib import Path
from PIL import Image
T = Path(__file__).resolve().parents[1]
RT = {k: next((T / 'ab').glob(f'runtime-{t}-*')) for k, t in (('A', 'VA'), ('B', 'VB'), ('C', 'VC'), ('G', 'VG'))}
PICK = [('A', 4), ('B', 4), ('C', 4), ('G', 4), ('A', 5), ('C', 5), ('G', 5), ('G', 6)]
FAR = (240, 280, 1040, 420)
s = Image.new('RGB', (1600, 4 * 144))
for j, (k, i) in enumerate(PICK):
    s.paste(Image.open(RT[k] / 'frames' / f'frame_{i:03d}.bmp').convert('RGB').crop(FAR), (800 * (j % 2), 144 * (j // 2)))
s.save(T / 'img' / 'corrected_far.png')
V = (440, 340, 840, 720)
s = Image.new('RGB', (1600, 380))
for j, (k, i) in enumerate([('A', 4), ('B', 4), ('C', 4), ('G', 4)]):
    s.paste(Image.open(RT[k] / 'frames' / f'frame_{i:03d}.bmp').convert('RGB').crop(V), (400 * j, 0))
s.save(T / 'img' / 'corrected_vehicle.png')
fr = next((RT['G'] / 'rsxi/frames').iterdir())
Image.open(next(fr.glob('snap*_end_op9999_bb_*'))).convert('RGB').save(T / 'img' / 'G_cap_bb.png')
