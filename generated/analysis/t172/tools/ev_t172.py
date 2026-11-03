"""T172: draw summary of captures. usage: py -3 ev_t172.py <frame dir> [op_lo op_hi]"""
import glob, json, sys

d = sys.argv[1]
lo, hi = int(sys.argv[2]) if len(sys.argv) > 2 else 0, int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9
rows = []
for l in open(glob.glob(d + '/events.jsonl*')[0], encoding='utf-8', errors='replace'):
    try:
        if l.startswith('{'):
            rows.append(json.loads(l))
    except ValueError:
        pass
print('rows', len(rows), 'kinds', sorted({r.get('e') for r in rows}))
print(open(glob.glob(d + '/events.jsonl*')[0], encoding='utf-8', errors='replace').readline()[:200])
last = None
for r in rows:
    if r.get('e') == 'snapshot' and lo <= (r.get('after_op') or 0) <= hi:
        print('  SNAP', r['after_op'], r['addr'], r['file'], r['nonzero_fraction'])
    g = r.get('guest')
    if not g or not lo <= r['op'] <= hi:
        continue
    k = (g['fp'], g['rt'], g['zeta'], str(g['depth']), str(g['stencil']), g['blend'], g['cmask'], g['cmd_offset'] if 0 else 0)
    if k != last:
        print(r['op'], g['fp'], 'vs', g['vs_hash'], 'rt', g['rt'], 'z', g['zeta'], 'vp', g['viewport'], 'n', g['count'], 'prim', g['prim'], 'bl', g['blend'], g.get('blend_key'), 'cm', g['cmask'],
              'd', g['depth'], 's', g['stencil'], 'cull', g['cull'], 'al', g['alpha'], 'cmd', g['cmd_offset'], 'remap', g.get('wpos_remap'))
        last = k
