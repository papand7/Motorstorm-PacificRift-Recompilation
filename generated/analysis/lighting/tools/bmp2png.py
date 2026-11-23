"""Lossless: each shot_*.bmp in the given dirs becomes shot_*.png (pixels verified equal), then the .bmp is removed.
usage: py -3 bmp2png.py <dir>..."""
import sys, pathlib
from PIL import Image, ImageChops
for d in sys.argv[1:]:
    n = 0; saved = 0
    for b in sorted(pathlib.Path(d).glob('shot_*.bmp')):
        if b.stat().st_size < 100: continue          # broken (disk full) files stay for the record
        p = b.with_suffix('.png')
        try:
            im = Image.open(b).convert("RGB")
        except OSError:
            continue                                  # truncated (disk full): left as it is
        im.save(p, optimize=False, compress_level=6)
        if ImageChops.difference(im, Image.open(p).convert('RGB')).getbbox() is None:
            saved += b.stat().st_size - p.stat().st_size; b.unlink(); n += 1
        else:
            p.unlink()
    print(d, n, 'converted', saved >> 20, 'MB freed')
