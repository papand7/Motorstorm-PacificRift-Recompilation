"""T145: race shader inventory from RSXI captures (hashes and metadata only).

  python inventory.py <out.json> <rsxi_dir>[:frame,...] ...

Per fragment program: instruction count, texture units the body fetches (and
how), inputs read, colour targets, predication / kill / pack / perspective /
facing / depth export, per-draw colour transfers the guest asks for
(srgb_output, gamma and expand masks on fetched units), surface formats and
the render passes (colour target addresses) it draws into.
Per vertex program: instruction count, attributes read, outputs written.
"""
import json, re, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 't113' / 'tools'))
from ev import events

FETCH = re.compile(r'rsx_tex\[?(\d+)\]?\.(Sample|SampleBias|SampleLevel|SampleGrad)\b')
SHADOW = re.compile(r'_rsx_shadow(\d+)\(')
INPUTS = re.compile(r'input\.(position|col0|col1|fog|tc\d|_rsx_front)')


def fp_meta(text):
    head = text.split('\n', 1)[0]
    m = re.search(r'instrs=(\d+)', head)
    body = text[text.find(' main('):] if ' main(' in text else text
    units = collections.defaultdict(set)
    for u, how in FETCH.findall(body):
        units[int(u)].add(how)
    for u in SHADOW.findall(body):
        units[int(u)].add('shadow')
    bx2 = len(re.findall(r'_rsx_expand_input\([^;]*, 15u, true\)', body))
    tg = re.findall(r'_out\.t(\d) =', body)
    return {
        'instrs': int(m.group(1)) if m else None,
        'units': {str(k): sorted(v) for k, v in sorted(units.items())},
        'inputs': sorted(set(INPUTS.findall(body))),
        'targets': (max(int(t) for t in tg) + 1) if tg else 1,
        'depth_export': '_out.depth' in body,
        'export_file': 'h' if re.search(r'_o0? = h\[', body) else 'r',
        'predicated': '_p = (float4)((cc' in body or 'if (cc' in body,
        'kill': body.count('discard'),
        'alias_sync': body.count('_rsx_pk2h(h[') + body.count('= _rsx_up2h(r['),
        'pack_ops': len(re.findall(r'_rsx_(pk|up)(4ub|4b|2us|2h)\((?!h\[|r\[\d+\]\.\w\))', body)),
        'persp': '_rsx_inv_w(' in body,
        'bx2_fetches': bx2,
        'divsq': body.count('/ sqrt(abs('),
        'rsq': body.count('rsqrt(abs('),
        'lg2_ex2_pow': len(re.findall(r'\b(log2|exp2|pow)\(', body)),
        'ddx_ddy': len(re.findall(r'\bdd[xy]\(', body)),
        'todo': body.count('TODO'),
        'nan_guard': body.count('== _o'),
    }


def vp_meta(text):
    head = text.split('\n', 1)[0]
    m = re.search(r'instrs=(\d+)', head)
    body = text[text.find(' main('):]
    body = body[body.find('cc[1] = (float4)0;'):]
    attrs = sorted({int(a) for a in re.findall(r'\bv\[(\d+)\]', body)})
    outs = sorted({int(a) for a in re.findall(r'\bo\[(\d+)\]\.', body)})
    return {'instrs': int(m.group(1)) if m else None, 'attrs': attrs, 'outputs': outs,
            'addr_reg': 'a0' in body.replace('int4 a0', ''),
            'branches': len(re.findall(r'\bif \(', body))}


def main():
    out = sys.argv[1]
    fps, vps = {}, {}
    draws = []
    for spec in sys.argv[2:]:
        d, _, fr = spec.partition(':')
        d = Path(d)
        frames = sorted((d / 'frames').glob('f*')) if not fr else [d / 'frames' / ('f%06d' % int(x)) for x in fr.split(',')]
        for f in frames:
            ev = f / 'events.jsonl'
            if not ev.exists():
                continue
            for e in events(ev):
                k = e.get('e')
                if k == 'shader' and e.get('hlsl'):
                    p = d / e['hlsl']
                    if e['fp'] not in fps and p.exists():
                        fps[e['fp']] = dict(code_hash=e.get('code_hash'), decompile=e.get('decompile'),
                                            **fp_meta(p.read_text(errors='replace')))
                    elif e['fp'] not in fps:
                        fps[e['fp']] = dict(code_hash=e.get('code_hash'), decompile=e.get('decompile'))
                elif k == 'vshader' and e.get('hlsl'):
                    p = d / e['hlsl']
                    if e['vs_hash'] not in vps and p.exists():
                        vps[e['vs_hash']] = vp_meta(p.read_text(errors='replace'))
                elif k == 'draw':
                    g = e['guest']
                    tex = {t['unit']: t['req'] for t in e.get('tex', []) if t.get('req')}
                    draws.append(dict(cap=d.parent.name, frame=f.name, op=e['op'], fp=g.get('fp'),
                                      vs=g.get('vs_hash'), rt=g.get('rt'), mrt=g.get('mrt'), rt_fmt=g.get('rt_fmt'),
                                      srgb=g.get('srgb_output'), packer=g.get('shader_packer'), ctrl=g.get('shader_control'),
                                      blend=g.get('blend'), count=g.get('count'), pso=e.get('native', {}).get('pso'),
                                      tex={u: dict(fmt=t.get('fmt'), gamma=t.get('gamma_mask', 0), expand=t.get('expand_mask', 0),
                                                   w=t.get('w'), h=t.get('h'), cube=t.get('cube'), control0=t.get('control0'),
                                                   address=t.get('address'), filter=t.get('filter')) for u, t in tex.items()}))
    # per-FP draw aggregation
    for fp, m in fps.items():
        ds = [x for x in draws if x['fp'] == fp]
        fetched = {int(u) for u in m.get('units', {})}
        m['draws'] = len(ds)
        m['passes'] = sorted({x['rt'] for x in ds})
        m['rt_fmts'] = sorted({x['rt_fmt'] for x in ds if x['rt_fmt'] is not None})
        m['srgb_output_draws'] = sum(1 for x in ds if x['srgb'])
        gm = collections.Counter()
        em = collections.Counter()
        for x in ds:
            for u, t in x['tex'].items():
                if u in fetched and t['gamma']:
                    gm['u%d:%d' % (u, t['gamma'])] += 1
                if u in fetched and t['expand']:
                    em['u%d:%d' % (u, t['expand'])] += 1
        m['gamma_fetch_draws'] = dict(gm)
        m['expand_fetch_draws'] = dict(em)
        m['tex_fmts'] = sorted({'u%d:%s' % (u, t['fmt']) for x in ds for u, t in x['tex'].items() if u in fetched})
        m['ctrl'] = sorted({x['ctrl'] for x in ds})
    Path(out).write_text(json.dumps(dict(fps=fps, vps=vps, draws=draws), indent=1), encoding='utf-8')
    tot = len(draws)
    print('draws', tot, 'fps', len(fps), 'vps', len(vps))
    print('draws asking sRGB output', sum(1 for x in draws if x['srgb']))
    gd = sum(1 for x in draws if any(fps.get(x['fp'], {}).get('units', {}).get(str(u)) and t['gamma'] for u, t in x['tex'].items()))
    print('draws fetching a gamma unit', gd)
    ed = sum(1 for x in draws if any(fps.get(x['fp'], {}).get('units', {}).get(str(u)) and t['expand'] for u, t in x['tex'].items()))
    print('draws fetching an expand unit', ed)


if __name__ == '__main__':
    main()
