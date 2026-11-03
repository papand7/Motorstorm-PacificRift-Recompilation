MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T120: print guest zeta/depth/textures of selected RSXI ops."""
import sys, json
sys.path.insert(0, (MS_ROOT + r'\generated\analysis\t113\tools'))
from ev import events
want = {int(x) for x in sys.argv[2].split(',')}
for e in events(sys.argv[1]):
    if e.get('op') in want and e.get('e') == 'draw':
        g = e['guest']
        print(e['op'], g['fp'], 'rt', g['rt'], 'zeta', g['zeta'], 'depth', g['depth'], 'stencil', g['stencil'])
        for k in ('tex', 'textures', 'native'):
            if k in e: print('   ', k, json.dumps(e[k])[:900])
