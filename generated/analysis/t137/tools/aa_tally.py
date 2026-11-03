"""T137: per-frame tally of SET_SURFACE_FORMAT antialias per render target, and of every texture
binding that reads an antialiased target (size, window, source kind), from RSXI events.jsonl.

usage: python aa_tally.py <events.jsonl> [...]
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't113', 'tools'))
from ev import events

AA = {0: 'CENTER_1', 3: 'DIAGONAL_CENTERED_2', 4: 'SQUARE_CENTERED_4', 5: 'SQUARE_ROTATED_4'}
for p in sys.argv[1:]:
    rts = collections.Counter(); zeta = collections.Counter(); reads = collections.Counter()
    aa_of = {}; ops = collections.defaultdict(list); aactl = collections.Counter(); clears = collections.Counter()
    for e in events(p):
        if e.get('e') != 'draw':
            if e.get('e') in ('clear',): clears[str(e)[:120]] += 1
            continue
        g = e['guest']; aa = (g['rt_fmt'] >> 12) & 0xF
        k = (g['rt'], g['rt_w'], g['rt_h'], g['color_pitch'], aa, g['rt_fmt'] & 0x1F, (g['rt_fmt'] >> 5) & 7)
        rts[k] += 1; aa_of[g['rt']] = aa; ops[g['rt']].append(e['op'])
        for m in g.get('mrt', []):
            if m != '0x00000000': aa_of.setdefault(m, aa)
        zeta[(g['zeta'], aa, g['depth']['test'], g['depth']['write'])] += 1
        if 'aa_ctl' in g: aactl[(g['aa_ctl']['value'], g['aa_ctl']['set'])] += 1
        for t in e.get('tex', []):
            r = t['req']
            if not r.get('set'): continue
            if t.get('src') in ('rt_exact', 'rt', 'rt_window', 'zeta', 'zeta_as_color') or 'rt' in str(t.get('src')) or 'zeta' in str(t.get('src')):
                reads[(t['src'], r['addr'], r['w'], r['h'], r['fmt'], r['pitch'], g['rt'], g['fp'])] += 1
    print('==', p)
    print('render targets (rt, w, h, pitch, antialias, colour fmt, zeta fmt): draws, op range')
    for k, v in sorted(rts.items()):
        o = ops[k[0]]
        print('  %4d  %s %s  ops %d..%d' % (v, k, AA.get(k[4], '?'), min(o), max(o)))
    print('zeta (addr, rt antialias, test, write): draws')
    for k, v in sorted(zeta.items()): print('  %4d  %s' % (v, k))
    print('aa_ctl:', dict(aactl) or 'not recorded (capture predates T133)')
    print('RT/zeta reads (src, addr, w, h, fmt, pitch, reading draw rt, fp): draws')
    for k, v in sorted(reads.items()): print('  %4d  %s' % (v, k))
