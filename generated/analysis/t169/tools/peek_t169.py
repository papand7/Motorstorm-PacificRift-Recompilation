import sys, json, collections
from rsxi_parse_t169 import read_events
st = {}
ev = list(read_events(sys.argv[1], st))
print(st)
print(collections.Counter(e['e'] for e in ev))
draws = [e for e in ev if e['e'] == 'draw']
d = draws[300]
print(list(d.keys()))
print(json.dumps(d.get('tex', [])[:2])[:1600])
print(sorted(d['guest'].keys()))
for k in set(e['e'] for e in ev):
    if k != 'draw':
        print(k, json.dumps(next(e for e in ev if e['e'] == k))[:500])
# pass graph
print('--- passes')
cur = None
for e in draws:
    g = e['guest']
    key = (g['rt'], g['rt_fmt'], g['rt_w'], g['rt_h'], g.get('zeta'), g.get('srgb_output'), g['mrt'][0])
    if key != cur:
        if cur: print(f"op{first}-{last} n={n} rt={cur[0]} fmt={cur[1]:#x} {cur[2]}x{cur[3]} z={cur[4]} srgb={cur[5]} mrt0={cur[6]} blend={sorted(bl)} fps={sorted(fp)[:6]}")
        cur = key; first = e['op']; n = 0; bl = set(); fp = set()
    n += 1; last = e['op']; bl.add(g.get('blend_key')); fp.add(g['fp'])
print(f"op{first}-{last} n={n} rt={cur[0]} fmt={cur[1]:#x} {cur[2]}x{cur[3]} z={cur[4]} srgb={cur[5]} mrt0={cur[6]} blend={sorted(bl)} fps={sorted(fp)[:6]}")
# sampler census
print('--- samplers')
c = collections.Counter()
for e in draws:
    for t in e.get('tex', []):
        q = t.get('req', {})
        if q.get('set'):
            c[(t['unit'], q.get('fmt'), q.get('filter'), q.get('address'), q.get('mips'), q.get('gamma_mask'), t.get('sampler') or t.get('host_sampler'), t.get('src'))] += 1
for k, v in c.most_common(45):
    print(v, k)
