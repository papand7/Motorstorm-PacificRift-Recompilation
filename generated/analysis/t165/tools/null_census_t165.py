"""T165: which texture units resolve to a null SRV in RSXI draws, on which target, and whether the fragment
program actually samples them (scanned from the dumped HLSL). usage: null_census_t165.py <rsxi_dir> [...]"""
import collections, glob, json, os, re, sys
for d in sys.argv[1:]:
    c = collections.Counter(); ex = {}
    for p in sorted(glob.glob(os.path.join(d, 'frames', '*', 'events.jsonl'))):
        for line in open(p, encoding='utf-8', errors='replace'):
            try: e = json.loads(line)
            except ValueError: continue
            if e.get('e') != 'draw': continue
            g = e['guest']; fp = g.get('fp', '')
            hp = os.path.join(d, 'shaders', 'fp_%s.hlsl' % fp[2:])
            src = open(hp, errors='replace').read() if os.path.exists(hp) else ''
            for t in e.get('tex', []):
                if t.get('src') != 'null_srv': continue
                u = t['unit']; r = t.get('req', {})
                used = ('rsx_tex[%d]' % u) in src or ('rsx_shadow_%d' % u) in src or ('_rsx_shadow%d' % u) in src
                k = (g.get('rt'), u, r.get('fmt'), r.get('addr'), 'sampled' if used else ('no-hlsl' if not src else 'unused'))
                c[k] += 1; ex.setdefault(k, (fp, t.get('native')))
    print('==', d, sum(c.values()))
    for k, v in c.most_common(30): print('  %5d' % v, *k, ex[k])
