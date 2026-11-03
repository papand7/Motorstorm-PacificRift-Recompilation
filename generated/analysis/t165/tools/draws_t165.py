"""T165: per-frame draw table from an RSXI events.jsonl (or .part): one row per (fp, vs, target) group, with
draw count, vertices, alpha/blend/cull/depth state, transfers and texture formats, filters and sources.
usage: py -3 draws_t165.py <events.jsonl[.part]> [--rt 0x00750000]"""
import collections, json, sys, re
NAN = re.compile(r'-?nan(?:\(ind\))?|-?inf')   # RSXI prints non-finite constants bare; plain json.loads drops those draws


def events(p):
    for line in open(p, encoding='utf-8', errors='replace'):
        try:
            yield json.loads(NAN.sub('NaN', line))
        except ValueError:
            continue


def main(a):
    rt = a[a.index('--rt') + 1] if '--rt' in a else None
    g = collections.OrderedDict()
    kinds = collections.Counter()
    last_op = None
    for e in events(a[0]):
        kinds[e.get('e')] += 1
        if e.get('e') != 'draw':
            continue
        d = e['guest']
        last_op = e['op']
        if rt and d['rt'] != rt:
            continue
        k = (d['fp'], d['vs_hash'], d['rt'])
        r = g.setdefault(k, dict(n=0, v=0, first=e['op'], alpha=set(), blend=set(), cull=set(), depth=set(), xfer=set(), tex={}))
        r['n'] += 1
        r['v'] += d.get('count', 0)
        r['alpha'].add(d.get('alpha'))
        r['blend'].add((d.get('blend'), d.get('blend_key')))
        r['cull'].add((d.get('cull'), d.get('raster', {}).get('cull_face')))
        r['depth'].add((d['depth']['test'], d['depth']['write'], d['depth']['func']))
        r['xfer'].add((d.get('srgb_output'), d.get('host_xfer')))
        for t in e.get('tex', []):
            q = t.get('req', {})
            if q.get('set'):
                r['tex'].setdefault(t['unit'], set()).add((q.get('fmt'), q.get('filter'), q.get('address'), q.get('mips'), q.get('gamma_mask'), t.get('src')))
    print('kinds', dict(kinds), 'last_op', last_op)
    for k, r in g.items():
        print(f"{k[0]} vs={k[1]} rt={k[2]} first_op={r['first']} draws={r['n']} verts={r['v']} alpha={sorted(map(str, r['alpha']))} "
              f"blend={sorted(map(str, r['blend']))[:2]} cull={sorted(map(str, r['cull']))} depth={sorted(map(str, r['depth']))} xfer={sorted(map(str, r['xfer']))}")
        for u in sorted(r['tex']):
            s = sorted(map(str, r['tex'][u]))
            print(f"    t{u} n={len(s)} {s[:2]}")


main(sys.argv[1:])
