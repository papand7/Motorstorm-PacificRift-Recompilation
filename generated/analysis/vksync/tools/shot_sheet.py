r"""RSX_SHOTS frames -> contact sheets and a frame-to-frame change list.
usage: py -3 shot_sheet.py <shots dir> <out dir> [first] [count] [cols] [scale]
Writes <out>/sheet_<first>.png (count consecutive frames, numbered) and prints, for every frame in the dir,
the mean absolute change from the previous frame (whole image and lower half, where the ground and the
shadows are), so jumps stand out."""
import sys
import pathlib
from PIL import Image, ImageChops, ImageDraw, ImageStat

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
files = sorted(src.glob('shot_*.bmp'))
num = lambda f: int(f.stem.split('_')[1])

if len(sys.argv) > 3:
    first, count = int(sys.argv[3]), int(sys.argv[4])
    cols = int(sys.argv[5]) if len(sys.argv) > 5 else 4
    scale = float(sys.argv[6]) if len(sys.argv) > 6 else 0.25
    sel = [f for f in files if first <= num(f) < first + count]
    ims = [Image.open(f).convert('RGB') for f in sel]
    w, h = int(ims[0].width * scale), int(ims[0].height * scale)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w, rows * h))
    d = ImageDraw.Draw(sheet)
    for i, (f, im) in enumerate(zip(sel, ims)):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(im.resize((w, h), Image.LANCZOS), (x, y))
        d.text((x + 4, y + 4), str(num(f)), fill=(255, 255, 0))
    p = out / f'sheet_{first}.png'
    sheet.save(p)
    print(p)
else:
    prev = None
    for f in files:
        im = Image.open(f).convert('L').resize((480, 270))
        if prev is not None and num(f) == num(prev[0]) + 1:
            dd = ImageChops.difference(im, prev[1])
            whole = ImageStat.Stat(dd).mean[0]
            low = ImageStat.Stat(dd.crop((0, 135, 480, 270))).mean[0]
            print(f'{num(f)} {whole:6.2f} {low:6.2f}')
        prev = (f, im)
