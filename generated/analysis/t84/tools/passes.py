#!/usr/bin/env python3
"""T84: per-pass summary of an RSXI frame (offline, read-only). A pass is a run of consecutive draws
with the same colour target and zeta. Per pass: op range, target/zeta, size, draws, draws per VS,
samples passed (RSXI_OCC ops only) and the pass snapshot's non-zero fraction.
  py -3 -I passes.py <rsxi frame dir>"""
import collections, json, re, sys
from pathlib import Path


def main(fd):
    ev = [json.loads(re.sub(r'-?(?:nan|inf)', 'null', l))
          for l in (Path(fd) / 'events.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    occ = {e['op']: e['samples_passed'] for e in ev if e['e'] == 'occlusion'}
    snap = {e['after_op']: (e['addr'], e['nonzero_fraction']) for e in ev if e['e'] == 'snapshot' and e['kind'] == 'pass'}
    passes = []
    for e in ev:
        if e['e'] != 'draw':
            continue
        g = e['guest']
        key = (g['rt'], g['zeta'], g['rt_w'], g['rt_h'])
        if not passes or passes[-1]['key'] != key:
            passes.append({'key': key, 'ops': [], 'vs': collections.Counter(), 'occ': 0, 'occ_n': 0})
        p = passes[-1]
        p['ops'].append(e['op'])
        p['vs'][g['vs_hash'][2:]] += 1
        if e['op'] in occ:
            p['occ'] += occ[e['op']]
            p['occ_n'] += 1
    for p in passes:
        rt, z, w, h = p['key']
        lo, hi = p['ops'][0], p['ops'][-1]
        s = [f'{a[2:]}:{f:.3f}' for op, (a, f) in snap.items() if lo <= op <= hi + 1]
        oc = f"{p['occ']} ({p['occ_n']} ops)" if p['occ_n'] else '-'
        print(f"ops {lo:3d}-{hi:3d}  rt={rt[2:]} zeta={z[2:]} {w}x{h}  draws={len(p['ops']):3d}  samples={oc}"
              f"  vs={dict(p['vs'])}  snap={' '.join(s) or '-'}")


if __name__ == '__main__':
    main(sys.argv[1])
