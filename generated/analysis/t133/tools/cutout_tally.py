"""T133: race draws whose guest FP discards (KIL), the units those FPs sample, and their sampler state.

usage: python cutout_tally.py <frame_dir_with_events.jsonl> <shader_dir>
"""
import sys, os, re, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't113', 'tools'))
sys.path.insert(0, os.path.dirname(__file__))
from ev import events
from tex_tally import dec

fr, sd = sys.argv[1], sys.argv[2]
kil = {}
for n in os.listdir(sd):
    if not n.startswith('fp_'): continue
    s = open(os.path.join(sd, n), encoding='utf-8', errors='replace').read()
    if 'discard' in s:
        kil[n[3:11].upper()] = sorted(set(int(u) for u in re.findall(r'rsx_tex\[(\d+)\]\.Sample', s)))
rows = collections.Counter(); per_rt = collections.Counter(); n = 0
for e in events(os.path.join(fr, 'events.jsonl')):
    g = e.get('guest')
    if not g: continue
    fp = g['fp'][2:].upper()
    if fp not in kil: continue
    n += 1
    per_rt[(g['rt'], g['fp'], g['blend'], g['cmask'])] += 1
    for t in e.get('tex', []):
        if t['unit'] in kil[fp] and t['req'].get('set'):
            d = dec(t)
            rows[(g['fp'], t['unit'], d['fmt'], '%dx%d' % (d['w'], d['h']), d['mips'], d['min'], d['mag'],
                  d['host'], round(d['bias'], 3), d['maxlod'], d['wrap'][:2])] += 1
print('KIL FPs in shader dir: %d; draws using them: %d' % (len(kil), n))
print('\n(rt, fp, blend, cmask):')
for k, v in sorted(per_rt.items()): print('  %4d %s' % (v, k))
print('\n(fp, unit, fmt, size, mips, min, mag, host, bias, maxlod, wrap):')
for k, v in sorted(rows.items()): print('  %4d %s' % (v, k))
