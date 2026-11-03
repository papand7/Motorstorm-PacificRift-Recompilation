"""T172: which VP constants D1 recorded for the boxes; crops of VA/VB. Run from t169/tools (PIL). usage: py -3 vpc_t172.py"""
import glob, sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, '.')
from rsxi_parse_t169 import read_events

d = glob.glob('../ab/runtime-D1-*/rsxi/frames/f005110')[0]
rows = list(read_events(glob.glob(d + '/events.jsonl*')[0]))
box = [r for r in rows if r.get('e') == 'draw' and r['guest']['fp'] == '0x022C20C1']
for b in box[:2] + box[-2:]:
    print(b['op'], 'n', b['guest'].get('vp_consts_nonzero'), [c[0] for c in b['guest']['vp_consts']])
    print('  c256-', [c for c in b['guest']['vp_consts'] if c[0] >= 256][:12])
    print('  geom', {k: v for k, v in b['guest']['geom'].items() if k in ('index', 'a0', 'input')})
    print('  native', b['native'])
OUT = Path('../../t172/img')
o = Image.new('RGB', (1280, 1000), (255, 0, 255))
for i, tag in enumerate(('VA', 'VB')):
    f = sorted(glob.glob(f'../ab/runtime-{tag}-*/frames/*.bmp'))
    o.paste(Image.open(f[6]).convert('RGB').crop((0, 250, 1280, 745)), (0, i * 505))
o.save(OUT / 'VA_VB_f6.png')
