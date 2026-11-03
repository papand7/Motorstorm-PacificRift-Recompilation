"""T141: one line per draw of an RSXI frame: target, MRT, blend key, mask, depth/stencil, and its texture sources.
usage: python ops.py <events.jsonl> [first_op last_op]"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't113', 'tools'))
from ev import events
a, b = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 1 << 30)
for e in events(sys.argv[1]):
    if e.get('e') != 'draw' or not (a <= e['op'] <= b): continue
    g = e['guest']
    mrt = ','.join(m[-6:-4] for m in g['mrt'] if m != '0x00000000')
    tx = ' '.join('%d:%s%s/%s%dx%d' % (t['unit'], t['req']['addr'][-6:-4], '' , t['src'][:6], t['req']['w'], t['req']['h'])
                  for t in e.get('tex', []) if t['req'].get('set') and t['src'] in ('rt_exact', 'zeta_as_color', 'zeta'))
    d, s = g['depth'], g['stencil']
    print('%4d %s fp%s rt%s fmt%04X%s vp%s bl%d/%s cm%X d%d%d%d s%d/%d %s sc%s' % (
        e['op'], g['cmd_offset'][-6:], g['fp'][2:], g['rt'][-6:-4], g['rt_fmt'], ('+' + mrt) if mrt else '',
        g['viewport'], g['blend'], g['blend_key'][2:], g['cmask'], d['test'], d['write'], d['func'], s['test'], s['func'], tx, g['shader_control'][2:]))
