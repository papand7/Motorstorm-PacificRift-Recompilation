#!/usr/bin/env python3
"""T84: one line per RSXI op of a captured frame (offline, read-only).
op, kind, prim/count, VS/FP, colour target(s), zeta, guest depth {test,write,func}, guest stencil,
blend, cmask, cull, native PSO kind, occlusion samples, sampled guest surfaces (unit:addr:src),
and pass snapshots with their non-zero fraction.
  py -3 -I optable.py <rsxi frame dir> [first_op last_op]"""
import json, re, sys
from pathlib import Path

FUNCS = {0: 'NEVER', 1: 'LESS', 2: 'EQUAL', 3: 'LEQUAL', 4: 'GREATER', 5: 'NOTEQUAL', 6: 'GEQUAL', 7: 'ALWAYS'}


def load(fd):
    return [json.loads(re.sub(r'-?(?:nan|inf)', 'null', l))
            for l in (Path(fd) / 'events.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]


def short(a):
    return a[2:].lstrip('0') or '0' if isinstance(a, str) and a.startswith('0x') else str(a)


def main(fd, lo=0, hi=1 << 30):
    ev = load(fd)
    occ = {e['op']: e['samples_passed'] for e in ev if e['e'] == 'occlusion'}
    snaps = {}
    for e in ev:
        if e['e'] == 'snapshot' and e.get('kind') == 'pass':
            snaps.setdefault(e['after_op'], []).append(f"{short(e['addr'])}:{e['nonzero_fraction']:.3f}")
    for e in ev:
        op = e.get('op')
        if op is None or not lo <= op <= hi:
            continue
        if e['e'] == 'bind_rt':
            print(f"{op:4d} BIND rt={short(e['guest_rt'])} mrt={','.join(short(m) for m in e['guest_mrt'] if m != '0x00000000') or '-'}"
                  f" {e['w']}x{e['h']} depth_cleared={int(e['depth_cleared'])}")
        elif e['e'] == 'clear':
            print(f"{op:4d} CLEAR rt={short(e['guest_rt'])} colour={e.get('color')} {e.get('native')}")
        elif e['e'] == 'draw':
            g, n = e['guest'], e.get('native', {})
            d, s = g['depth'], g['stencil']
            dep = f"z[{d['test']}{d['write']}{FUNCS.get(d['func'] & 7, d['func'])[:3]}]" if d['test'] else 'z[off]'
            st = f"s[{FUNCS.get(s['func'] & 7, s['func'])[:3]} r{s['ref']} m{s['mask']}]" if s['test'] else ''
            mrt = ','.join(short(m) for m in g['mrt'] if m != '0x00000000')
            tex = ' '.join(f"t{t['unit']}={short(t['req']['addr'])}/{t['src'][:6]}" for t in e.get('tex', [])
                           if t.get('req', {}).get('set') and t['src'] not in ('upload', 'null_srv'))
            o = occ.get(op)
            # T84 instrumentation (absent in older captures): FIFO packet offset, CALL return
            # (0 = main ring) and SET_SHADER_CONTROL.
            prov = ''
            if g.get('cmd_offset'):
                prov = (f" fifo={short(g['cmd_offset'])}"
                        f"{'/call' if g.get('call_ret', '0x00000000') != '0x00000000' else '/ring'}"
                        f" sc={short(g.get('shader_control', '0x0'))}")
            print(f"{op:4d} DRAW p{g['prim']}x{g['count']} vs={short(g['vs_hash'])} fp={short(g['fp'])}{prov}"
                  f" rt={short(g['rt'])}{'+' + mrt if mrt else ''} zt={short(g['zeta'])} {g['rt_w']}x{g['rt_h']}"
                  f" {dep} {st} bl={short(g['blend_key'])} cm={g['cmask']} cull={g['cull']}"
                  f" pso={n.get('pso', '?')} occ={'-' if o is None else o} {tex}")
        if op in snaps and e['e'] in ('draw', 'clear'):
            print(f"      snapshot after {op}: {' '.join(snaps.pop(op))}")


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], *(int(x) for x in a[1:3]))
