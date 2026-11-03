"""T169: draws whose depth/stencil request differs from the legacy guest-FP pipeline (writes on, LESS_EQUAL, no stencil).
usage: py -3 depth_census_t169.py <events.jsonl>"""
import collections, sys
from rsxi_parse_t169 import read_events

c = collections.Counter()
per_rt = collections.Counter()
for e in read_events(sys.argv[1]):
    if e['e'] != 'draw':
        continue
    g = e['guest']
    d, s = g['depth'], g.get('stencil', {})
    c['draws'] += 1
    wr = bool(d['test'] and not d['write'])
    fn = bool(d['test'] and d['func'] != 3)
    st = bool(s.get('test'))
    c['depth test on, write off (host writes)'] += wr
    c['compare not LEQUAL (host LEQUAL)'] += fn
    c['stencil test on (host none)'] += st
    c['any difference'] += wr or fn or st
    if wr or fn:
        per_rt[(g['rt'], g['fp'], d['func'], d['write'])] += 1
print(dict(c))
for k, v in per_rt.most_common(14):
    print(' ', v, k)
