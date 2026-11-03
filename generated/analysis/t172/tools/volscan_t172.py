"""T172: draws RSX_DEPTH_VOLUME would select in the captures with draw records, and box stencil refs. Run from t169/tools. usage: py -3 volscan_t172.py"""
import glob, sys
from collections import Counter
sys.path.insert(0, '.')
from rsxi_parse_t169 import read_events

for d in glob.glob('../../t171/ab/runtime-T*/rsxi/frames/*') + glob.glob('../ab/runtime-[DF]1-*/rsxi/frames/*') + glob.glob('../../t165/ab/runtime-B3-*/rsxi/frames/f002192'):
    rows = list(read_events(glob.glob(d + '/events.jsonl*')[0]))
    draws = [r['guest'] for r in rows if r.get('e') == 'draw']
    sel = Counter()
    for g in draws:
        dp = g['depth']
        if dp['test'] and not dp['write'] and dp['func'] in (4, 6):
            sel[(g['fp'], dp['func'], g['rt'])] += 1
    refs = sorted({g['stencil']['ref'] for g in draws if g['fp'] == '0x022C20C1'})
    print(d[-40:], 'draws', len(draws), 'selected', dict(sel), 'box refs', refs)
