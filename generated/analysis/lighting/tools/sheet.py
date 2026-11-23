r"""usage: py -3 sheet.py <out.png> <dir>:<index> ...   (2 columns, each frame 960 wide)"""
import sys, glob
from PIL import Image
out = sys.argv[1]
ims = []
for a in sys.argv[2:]:
    d, n = a.split(':')
    fs = sorted(glob.glob(d + '/shot_*.png') + glob.glob(d + '/shot_*.bmp'))
    ims.append(Image.open(fs[int(n)]).convert('RGB'))
w = 960
ims = [i.resize((w, int(i.height * w / i.width))) for i in ims]
rows = (len(ims) + 1) // 2
sheet = Image.new('RGB', (w * 2, ims[0].height * rows))
for k, i in enumerate(ims):
    sheet.paste(i, ((k % 2) * w, (k // 2) * ims[0].height))
sheet.save(out)
print(sheet.size)
