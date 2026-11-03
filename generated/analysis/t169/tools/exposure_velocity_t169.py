"""T169: c33 exposure per capture; export mode of the draws writing 0x01650000 after the bloom chain; channel
statistics of the RSXI pass snapshots of that surface, with the values the guest would read as Y16_X16_FLOAT.
usage: py -3 exposure_velocity_t169.py <t165/ab dir>"""
import glob, os, struct, sys
from PIL import Image
import numpy as np
from rsxi_parse_t169 import read_events

root = sys.argv[1]
for f in sorted(glob.glob(os.path.join(root, 'runtime-*/rsxi/frames/*/events.jsonl*'))):
    parts = f.replace('\\', '/').split('/')
    c33 = None
    for e in read_events(f):
        if e['e'] == 'draw':
            d = {c[0]: c[1:] for c in e['guest'].get('vp_consts', [])}
            if 33 in d:
                c33 = d[33]
                break
    print(parts[-5][:10], parts[-2], 'c33', c33)

b3 = glob.glob(os.path.join(root, 'runtime-B3-*/rsxi/frames/f002192'))[0]
ev = list(read_events(os.path.join(b3, 'events.jsonl')))
w = [e for e in ev if e['e'] == 'draw' and e['guest']['rt'] == '0x01650000']
print('draws on 0x01650000:', len(w), 'exp32', sorted({e['guest'].get('fp_exp32') for e in w}),
      'ctl', sorted({e['guest'].get('shader_control') for e in w})[:6], 'cmask', sorted({e['guest'].get('cmask') for e in w}),
      'fps', len({e['guest']['fp'] for e in w}))
print('clears:', [(e['op'], e.get('guest_rt'), e.get('color')) for e in ev if e['e'] == 'clear'])


def half(u):
    return struct.unpack('<e', struct.pack('<H', u))[0]


for s in sorted(glob.glob(os.path.join(b3, 'snap*rt_01650000*'))):
    a = np.asarray(Image.open(s).convert('RGBA')).astype(np.uint32)
    print(os.path.basename(s), 'mean RGB', a[..., :3].mean((0, 1)).round(1), 'p99', np.percentile(a[..., :3], 99, axis=(0, 1)),
          'zero frac', float((a[..., :3].sum(2) == 0).mean()))
    if 'op09' in s:
        # A8R8G8B8 word's bytes as RSX would present them: Y16_X16_FLOAT takes the 32-bit word's two halves.
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        host = np.sqrt((r / 255.) ** 2 + (g / 255.) ** 2)
        print('  host unorm |xy| mean', float(host.mean()), 'p99', float(np.percentile(host, 99)))
        print('  composite weight sat(100*|xy|) mean', float(np.clip(100 * host, 0, 1).mean()))
