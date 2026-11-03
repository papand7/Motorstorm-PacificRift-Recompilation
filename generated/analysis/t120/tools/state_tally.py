MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T120: tally guest depth/stencil/blend/MRT state per draw in an RSXI frame."""
import sys, collections
sys.path.insert(0, (MS_ROOT + r'\generated\analysis\t113\tools'))
from ev import events
c = collections.Counter(); ex = {}
for e in events(sys.argv[1]):
    if e.get('e') != 'draw': continue
    g = e['guest']; d = g['depth']; s = g['stencil']
    nmrt = sum(1 for m in g['mrt'] if m != '0x00000000')
    k = (f"dtest={d['test']} dwrite={d['write']} dfunc=0x{d['func']:02X}", f"stest={s['test']} sfunc={s['func']} ref={s['ref']} mask={s['mask']}", f"mrt={nmrt} blend={g['blend']} cmask={g['cmask']}")
    c[k] += 1; ex.setdefault(k, []).append(e['op'])
for k, n in sorted(c.items(), key=lambda x: -x[1]):
    print(n, ' | '.join(k), 'ops', ex[k][:8])
