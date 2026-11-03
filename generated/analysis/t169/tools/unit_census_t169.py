"""T169: census of the texture units a frame's fragment programs really sample (rsx_tex[n] in the dumped HLSL): guest
sampler against host sampler, mip levels against guest levels, null or depth-as-colour sources, disabled units,
and format reinterpretation of render targets.
usage: py -3 unit_census_t169.py <events.jsonl> <shader_dir> [more shader dirs]"""
import collections, glob, os, re, sys
from rsxi_parse_t169 import read_events

UNITS = re.compile(r'rsx_tex\[(\d+)\]')
paths, used, missing = sys.argv[1], {}, set()
dirs = sys.argv[2:]


def units_of(fp):
    key = fp[2:]
    if key not in used:
        used[key] = None
        for d in dirs:
            p = os.path.join(d, f'fp_{key}.hlsl')
            if os.path.exists(p):
                src = open(p, encoding='utf-8', errors='replace').read()
                body = src[src.find('main('):]
                used[key] = {int(x) for x in UNITS.findall(body)}
                break
    return used[key]


st = {}
draws = [e for e in read_events(paths, st) if e['e'] == 'draw']
print('parse', {k: st[k] for k in ('total', 'parsed', 'repaired', 'rejected')}, 'draws', len(draws))
samp, srcs, disabled, chain, fmts = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
no_hlsl = sampled = 0
sensitive = collections.Counter()
for e in draws:
    fp = e['guest']['fp']
    u = units_of(fp)
    if u is None:
        no_hlsl += 1
        missing.add(fp)
        continue
    for t in e.get('tex', []):
        q = t.get('req', {})
        if t['unit'] not in u or not q.get('set'):
            continue
        sampled += 1
        f = int(q['filter'], 16)
        a = int(q['address'], 16)
        c0 = int(q['control0'], 16)
        minf, magf = (f >> 16) & 7, (f >> 24) & 7
        wrap = a & 15
        guest = f"min{minf} mag{magf} wrap{wrap} bias{'-' if f & 0x1000 else ''}{bool(f & 0x1FFF)}"
        samp[(t['unit'] == 0, q.get('host_sampler'), guest)] += 1
        srcs[(t.get('src'),)] += 1
        if not c0 >> 31:
            disabled[(t['unit'], t.get('src'))] += 1
        if t.get('src') == 'upload':
            chain[('guest mips>1' if q.get('mips', 1) > 1 and minf >= 3 else 'no guest mips',)] += 1
            if q.get('mips', 1) > 1 and minf >= 3:
                sensitive[q['fmt']] += 1
        if t.get('src') in ('null_srv', 'zeta_as_color', 'rt_exact'):
            fmts[(t['src'], q['fmt'], t.get('native', {}).get('dxgi'), q.get('addr'), 'gamma' if q.get('gamma_mask') else 'nogamma', q.get('host_sampler'), guest)] += 1
print('sampled bindings', sampled, 'draws without HLSL', no_hlsl, 'fps', sorted(missing)[:20])
print('guest vs host sampler:')
for k, v in samp.most_common(25):
    print(' ', v, k)
print('sources:', srcs.most_common())
print('sampled while CONTROL0 enable clear (unit, src):', disabled.most_common(12))
print('upload bindings:', chain.most_common(), 'mip-filter formats', sensitive.most_common())
print('rt / zeta / null bindings:')
for k, v in fmts.most_common(40):
    print(' ', v, k)
