"""T144: tally guest stencil/depth state per draw from an RSXI frame (events.jsonl), and the
stencil writers/readers per zeta. Tolerates C-style nan/inf in the records.
py -3 -I stencil_usage.py <frame dir> [--seq]"""
import json, re, sys, collections
from pathlib import Path
fix = re.compile(r'(?<![A-Za-z"])-?(nan|inf)\b', re.I)
ev = []
for l in open(Path(sys.argv[1]) / 'events.jsonl', encoding='utf-8', errors='replace'):
    try: ev.append(json.loads(fix.sub('null', l)))
    except Exception: pass
F = {0: 'NEVER', 1: 'LESS', 2: 'EQUAL', 3: 'LEQUAL', 4: 'GREATER', 5: 'NOTEQUAL', 6: 'GEQUAL', 7: 'ALWAYS'}
c = collections.Counter(); per_z = collections.defaultdict(list); fps = collections.defaultdict(set)
draws = [e for e in ev if e.get('e') == 'draw']
for e in draws:
    g = e['guest']; s = g['stencil']; d = g['depth']
    k = (s['test'], F.get(s['func'] & 7, s['func']), s['ref'], s['mask'], d['test'], d['write'], d['func'] & 7, g.get('ds_key'))
    c[k] += 1; fps[k].add(g.get('fp'))
    if s['test']: per_z[g.get('zeta')].append((e['op'], s['ref'], F.get(s['func'] & 7), s['mask'], g.get('rt'), g.get('fp')))
print(f"draws={len(draws)} stencil_on={sum(v for k, v in c.items() if k[0])}")
for k, v in sorted(c.items(), key=lambda x: -x[1]):
    print(f"{v:4d} stencil test={k[0]} {k[1]} ref={k[2]} mask={k[3]} | depth test={k[4]} write={k[5]} func={k[6]} ds_key={k[7]} fps={len(fps[k])}")
for z, l in per_z.items():
    ops = [x[0] for x in l]
    print(f"zeta {z}: {len(l)} stencil draws, ops {min(ops)}-{max(ops)}; rts {sorted({x[4] for x in l})}")
if '--seq' in sys.argv:
    prev = None
    for e in ev:
        if e.get('e') == 'draw':
            g = e['guest']; s = g['stencil']
            k = (g.get('rt'), g.get('zeta'), s['test'], s['func'] & 7, s['ref'], s['mask'], g['depth']['test'], g['depth']['write'])
            if k != prev: print('draw', e['op'], k, g.get('fp'))
            prev = k
        elif e.get('e') in ('bind_rt', 'clear'):
            print(e['e'], e['op'], e.get('guest_rt'), 'depth_cleared=%s' % e.get('depth_cleared'), e.get('native', ''), e.get('zeta', ''))
            prev = None
