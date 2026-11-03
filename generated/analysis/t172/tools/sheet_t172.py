"""T172: contact sheets of the race dumps of earlier runs. Run from t169/tools (PIL). usage: py -3 sheet_t172.py"""
from pathlib import Path
from PIL import Image

A = Path('../../').resolve()
OUT = A / 't172' / 'img'
for tag, pat in (('VA', 't169/ab/runtime-VA-*'), ('VB', 't169/ab/runtime-VB-*'), ('D1', 't169/ab/runtime-D1-*'), ('F1', 't169/ab/runtime-F1-*')):
    rt = next(A.glob(pat))
    fs = sorted((rt / 'frames').glob('*.bmp'))
    W, H, C = 480, 270, 4
    o = Image.new('RGB', (W * C, H * ((len(fs) + C - 1) // C)))
    for i, f in enumerate(fs):
        o.paste(Image.open(f).convert('RGB').resize((W, H)), ((i % C) * W, (i // C) * H))
    o.save(OUT / f'sheet_{tag}.png')
    print(tag, len(fs))
