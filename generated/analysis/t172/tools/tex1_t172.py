"""T172: unit bindings of the box draws in the captures that record units. Run from t169/tools. usage: py -3 tex1_t172.py"""
import glob, json, sys
from collections import Counter
sys.path.insert(0, '.')
from rsxi_parse_t169 import read_events

for pat in ('../ab/runtime-D1-*/rsxi/frames/*', '../ab/runtime-F1-*/rsxi/frames/*', '../../t165/ab/runtime-B3-*/rsxi/frames/f002192'):
    for d in glob.glob(pat):
        rows = list(read_events(glob.glob(d + '/events.jsonl*')[0]))
        box = [r for r in rows if r.get('e') == 'draw' and r['guest']['fp'] == '0x022C20C1']
        print('==', d, 'boxes', len(box))
        c = Counter()
        for b in box:
            for t in b['tex'] or []:
                q, n = t['req'], t.get('native') or {}
                c[(t['unit'], q['addr'], q['w'], q['h'], q['fmt'], q['remap'], q['filter'], q['address'], q['mips'], t.get('src'), n.get('kind'), n.get('csum'), n.get('dxgi'))] += 1
        for k, v in sorted(c.items(), key=str):
            print(' ', v, k)
        all0 = Counter()
        for r in rows:
            for t in (r.get('tex') or []):
                if t['req']['fmt'] == '0x81':
                    all0[(t['req']['addr'], t['req']['w'], t['req']['h'], t['req']['remap'], (t.get('native') or {}).get('csum'), r['guest']['fp'])] += 1
        print('  0x81 uses', all0.most_common(10))
        for s in rows:
            if s.get('e') == 'shader' and '022C20C1' in json.dumps(s)[:200]:
                print('  shader', json.dumps(s)[:500])
