from PIL import Image
A = '../../'
B = A + 't165/ab/runtime-B3-20261030-125807/'
ims = [(B + 'rsxi/frames/f002192/snap18_pass_op0914_rt_01650000.bmp', (1000, 80, 1160, 170)), (B + 'frames/frame_002.bmp', (540, 430, 700, 520)), (A + 't145/ab/runtime-D1-20261028-183730/frames/frame_002.bmp', (880, 90, 1040, 180))]
c = Image.new('RGB', (1280, 1080))
y = 0
for f, b in ims:
    im = Image.open(f).convert('RGB')
    c.paste(im.resize((640, 360)), (0, y))
    c.paste(im.crop(b).resize((640, 360), Image.NEAREST), (640, y))
    y += 360
c.save('../logs/blue_candidates.png')
