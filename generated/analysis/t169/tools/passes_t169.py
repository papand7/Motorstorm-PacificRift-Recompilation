"""T169: per-draw state of an op range, mip availability and null-binding census of one RSXI frame.
usage: py -3 passes_t169.py <events.jsonl> <op_lo> <op_hi>"""
import collections, sys
from rsxi_parse_t169 import read_events

p, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
st = {}
ev = [e for e in read_events(p, st) if e['e'] == 'draw']
print(st)
for e in ev:
    if not lo <= e['op'] <= hi:
        continue
    g = e['guest']
    print(f"op{e['op']} off={g.get('cmd_offset')} rt={g['rt']} mrt0={g['mrt'][0]} z={g.get('zeta')} {g['rt_w']}x{g['rt_h']} fmt={g['rt_fmt']:#x} fp={g['fp']} n={g['count']} prim={g['prim']} blend={g.get('blend_key')} cmask={g.get('cmask')} cull={g.get('cull')} d={g['depth']} sten={g.get('stencil')} alpha={g.get('alpha')} srgb={g.get('srgb_output')} aa={g.get('aa_ctl', {}).get('value')} vp={g.get('viewport')}")
    for t in e.get('tex', []):
        q = t.get('req', {})
        if q.get('set'):
            print(f"   t{t['unit']} {q.get('addr')} {q.get('w')}x{q.get('h')} fmt={q.get('fmt')} mips={q.get('mips')} flt={q.get('filter')} adr={q.get('address')} ctl0={q.get('control0')} host={q.get('host_sampler')} gamma={q.get('gamma_mask')} src={t.get('src')} native={ {k: v for k, v in t.get('native', {}).items() if k != 'res'} }")
lv = collections.Counter()
null = collections.Counter()
hs = collections.Counter()
for e in ev:
    for t in e.get('tex', []):
        q = t.get('req', {})
        if not q.get('set'):
            continue
        n = t.get('native', {})
        if t.get('src') == 'upload':
            lv[(q.get('mips', 1) > 1, n.get('levels', n.get('mips', '?')))] += 1
        if t.get('src') in ('null_srv', 'zeta_as_color'):
            null[(t['src'], t['unit'], q.get('addr'), q.get('w'), q.get('h'), q.get('fmt'), e['guest']['fp'])] += 1
        hs[(t['unit'] == 0, q.get('host_sampler'), q.get('filter'), q.get('address'))] += 1
print('upload bindings (guest has mips, host levels):', lv)
print('null / zeta:')
for k, v in null.most_common(30):
    print(' ', v, k)
print('host sampler x guest (top 16):')
for k, v in hs.most_common(16):
    print(' ', v, k)
