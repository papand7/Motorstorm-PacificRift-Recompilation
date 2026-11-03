"""T169: image delta of the decal-box draws (fp 0x022C20C1) of an RSXI frame, from the pass snapshots around them.
usage: py -3 decal_delta_t169.py <frame dir> <out.png>"""
import glob, os, re, sys
import numpy as np
from PIL import Image
from rsxi_parse_t169 import read_events
D, out = sys.argv[1:3]
ev = glob.glob(os.path.join(D, 'events.jsonl*'))[0]
ops = []
samp = set()
for e in read_events(ev):
    if e['e'] == 'draw' and e['guest']['fp'] == '0x022C20C1':
        ops.append(e['op'])
        t = e['tex'][1]
        samp.add((t['req'].get('fmt'), t['req'].get('w'), t['req'].get('h'), t['req'].get('address'), t['req'].get('host_sampler')))
print('ops', ops[:1], ops[-1:], len(ops), 'unit 1:', sorted(samp)[:6])
snaps = sorted(glob.glob(os.path.join(D, 'snap*_rt_00750000*')), key=lambda s: int(re.search(r'op(\d+)', s).group(1)))
print([os.path.basename(s) for s in snaps][:8])
if ops:
    bef = [s for s in snaps if int(re.search(r'op(\d+)', s).group(1)) < ops[0]]
    aft = [s for s in snaps if int(re.search(r'op(\d+)', s).group(1)) >= ops[-1]]
    if bef and aft:
        a = np.asarray(Image.open(bef[-1]).convert('RGB')).astype(int)
        b = np.asarray(Image.open(aft[0]).convert('RGB')).astype(int)
        d = np.abs(b - a).sum(2)
        print(os.path.basename(bef[-1]), os.path.basename(aft[0]), 'changed', float((d > 0).mean()), 'mean', float(d.mean()))
        Image.fromarray(np.clip(d * 4, 0, 255).astype('uint8')).save(out)
