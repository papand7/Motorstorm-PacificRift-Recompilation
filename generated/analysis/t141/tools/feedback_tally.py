"""T141: draws that sample a colour surface they are writing (RT A or an MRT), counting only texture
units the draw's fragment program fetches (rsxi/shaders/fp_*.hlsl beside the frames dir).
usage: python feedback_tally.py <events.jsonl>"""
import sys, os, re, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't113', 'tools'))
from ev import events
path = sys.argv[1]
sd = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path)))), 'shaders')
units = {}
for f in os.listdir(sd):
    if f.startswith('fp_') and f.endswith('.hlsl'):
        h = open(os.path.join(sd, f), encoding='utf-8', errors='replace').read()
        units['0x' + f[3:11].upper()] = set(int(x) for m in re.findall(r'rsx_tex(?:\[(\d+)\]|(\d+))', h) for x in m if x)
rows = collections.OrderedDict()
for e in events(path):
    if e.get('e') != 'draw': continue
    g = e['guest']; fp = '0x' + g['fp'][2:].upper()
    outs = [g['rt']] + [m for m in g['mrt'] if m != '0x00000000']
    fu = units.get(fp)
    for t in e.get('tex', []):
        r = t['req']
        if not r.get('set') or r['addr'] not in outs: continue
        if fu is not None and t['unit'] not in fu: continue
        k = (fp, r['addr'], t['unit'], 'A' if r['addr'] == g['rt'] else 'MRT%d' % outs.index(r['addr']),
             '%dx%d' % (r['w'], r['h']), '%dx%d' % (g['rt_w'], g['rt_h']), g['rt_fmt'] >> 12 & 15, g['blend_key'], fu is not None)
        rows.setdefault(k, []).append(e['op'])
for k, ops in rows.items():
    print('fp %s reads %s unit %d (= its %s) as %s; surface %s aa%d blend %s fp_known=%s ops %d-%d (%d)' % (k + (ops[0], ops[-1], len(ops))))
