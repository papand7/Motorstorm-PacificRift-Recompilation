#!/usr/bin/env python3
"""T194: side-by-side contact sheet (one column per arm) and mean luma per frame dump.
  py -3 generated/analysis/t194/tools/sheet_t194.py <frames dir> [<frames dir> ...] <out.png>
Column order = argument order; each column is labelled with its runtime dir's arm letter."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageStat

dirs, out = [Path(a) for a in sys.argv[1:-1]], Path(sys.argv[-1])
lists = [sorted(d.glob('frame_*.bmp')) for d in dirs]
names = [d.parent.name.split('-')[1] if '-' in d.parent.name else d.name for d in dirs]
n = max(len(l) for l in lists)
W, H, T = 320, 180, 16
sheet = Image.new('RGB', (len(dirs) * (W + 8), T + n * (H + 4)), (40, 40, 40))
draw = ImageDraw.Draw(sheet)
for j, nm in enumerate(names):
    draw.text((j * (W + 8) + 4, 2), nm, fill=(255, 255, 0))
print('frame      ' + ' '.join(f'{nm:>7}' for nm in names))
for i in range(n):
    row = []
    for j, lst in enumerate(lists):
        if i < len(lst):
            im = Image.open(lst[i]).convert('RGB')
            row.append(f'{ImageStat.Stat(im.convert("L")).mean[0]:7.1f}')
            sheet.paste(im.resize((W, H)), (j * (W + 8), T + i * (H + 4)))
        else:
            row.append('      -')
    print(f'frame_{i:03d} ' + ' '.join(row))
sheet.save(out)
print('wrote', out)
