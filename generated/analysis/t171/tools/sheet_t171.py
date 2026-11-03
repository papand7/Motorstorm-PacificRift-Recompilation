"""T171: contact sheets of the race dumps of both arms. Run from t169/tools (PIL). usage: py -3 sheet_t171.py"""
from pathlib import Path
from PIL import Image

T = Path(r'../../t171').resolve()
for tag in ('TA', 'TB'):
    rt = next((T / 'ab').glob(f'runtime-{tag}-*'))
    fs = sorted((rt / 'frames').glob('*.bmp'))
    W, H, C = 640, 360, 3
    R = (len(fs) + C - 1) // C
    o = Image.new('RGB', (W * C, H * R))
    for i, f in enumerate(fs):
        o.paste(Image.open(f).convert('RGB').resize((W, H)), ((i % C) * W, (i // C) * H))
    (T / 'img').mkdir(exist_ok=True)
    o.save(T / 'img' / f'sheet_{tag}.png')
    print(tag, len(fs), [f.stat().st_mtime - fs[0].stat().st_mtime for f in fs])
