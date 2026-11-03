"""T165: cluster main-scene draws by the projected object origin (VP c0..c3 applied to 0,0,0,1) and report what each
vertex program's draws request: sRGB output, texture gamma, sign expansion, guest filter/address against the host
sampler, null or missing textures. Also tallies transfer requests per target.
usage: py -3 vehicle_state_t165.py <events.jsonl[.part]>"""
import collections, json, re, sys

NAN = re.compile(r'-?nan(?:\(ind\))?|-?inf')
vs = collections.OrderedDict()
rts = collections.Counter()
samp = collections.Counter()
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    try:
        e = json.loads(NAN.sub('NaN', line))
    except ValueError:
        continue
    if e.get('e') != 'draw':
        continue
    g = e['guest']
    rts[(g['rt'], hex(g.get('rt_fmt', 0)), g.get('srgb_output'), g.get('host_xfer'))] += 1
    for t in e.get('tex', []):
        q = t.get('req', {})
        if q.get('set') and g['rt'] == '0x00750000':
            f, a = int(q['filter'], 16), int(q['address'], 16)
            samp[(t['unit'], (f >> 16) & 7, (f >> 24) & 7, a & 15, (a >> 8) & 15, q.get('mips', 0) > 1, q.get('host_sampler'))] += 1
    if g['rt'] != '0x00750000':
        continue
    c = {k[0]: k[1:] for k in g.get('vp_consts', [])}
    org = None
    if all(i in c for i in range(4)) and c[3][3] > 0:
        vp_s, vp_o = g['raster']['vp_scale'], g['raster']['vp_offset']
        org = (round(c[0][3] / c[3][3] * vp_s[0] + vp_o[0]), round(c[1][3] / c[3][3] * vp_s[1] + vp_o[1]))
    r = vs.setdefault(g['vs_hash'], dict(n=0, ops=[e['op'], e['op']], srgb=0, gamma=0, expand=0, null=0, alpha=set(), org=collections.Counter()))
    r['n'] += 1
    r['ops'][1] = e['op']
    r['srgb'] += g.get('srgb_output', 0)
    r['alpha'].add(g.get('alpha'))
    r['org'][org] += 1
    tx = [t for t in e.get('tex', []) if t.get('req', {}).get('set')]
    r['gamma'] += any(t['req'].get('gamma_mask') for t in tx)
    r['expand'] += any(t['req'].get('expand_mask') for t in tx)
    r['null'] += any(t.get('src') in ('null', 'null_srv', 'none') for t in tx)
print('| vs | draws | ops | srgb_output | any gamma | any expand | null bound | alpha | top projected origins |')
print('|---|---|---|---|---|---|---|---|---|')
for k, r in vs.items():
    print(f"| {k} | {r['n']} | {r['ops'][0]}-{r['ops'][1]} | {r['srgb']} | {r['gamma']} | {r['expand']} | {r['null']} | {sorted(map(str, r['alpha']))} | {r['org'].most_common(3)} |")
print('\nper target (rt, fmt, srgb_output, host_xfer): draws')
for k, v in sorted(rts.items(), key=lambda x: -x[1])[:16]:
    print(k, v)
print('\nmain-scene sampler requests (unit, min, mag, wrap_s, wrap_t, has_mips, host_sampler): bindings')
for k, v in sorted(samp.items(), key=lambda x: -x[1])[:12]:
    print(k, v)
