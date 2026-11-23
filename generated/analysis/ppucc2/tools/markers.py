#!/usr/bin/env python3
"""ppucc2: count port patch markers (mspr/dist/slice/audio) per TU in two lifted trees; report differences.
  markers.py <twin dir> <lowered dir>"""
import re, sys
from pathlib import Path

TOK = ['mspr_patch_on(', 'mspr_audio_kick(', 'mspr_dist_f(', 'mspr_slice_ms(', 'MSPR_DIST', 'MSPR_PATCH=',
       'MSPR_SLICE_MS', 'extern "C"']
FN = re.compile(r'^void \w*func_[0-9A-F]{8}\(ppu_context\* ctx\) \{', re.M)


def counts(p):
    t = p.read_text(encoding='latin-1')
    c = {k: t.count(k) for k in TOK}
    c['functions'] = len(FN.findall(t))
    return c


a, b = Path(sys.argv[1]), Path(sys.argv[2])
tot_a, tot_b, bad = {}, {}, []
for f in sorted(a.glob('ppu_recomp*')):
    g = b / f.name
    if not g.exists():
        bad.append(f'{f.name}: missing'); continue
    ca, cb = counts(f), counts(g)
    for k in ca:
        tot_a[k] = tot_a.get(k, 0) + ca[k]; tot_b[k] = tot_b.get(k, 0) + cb[k]
        if k != 'extern "C"' and ca[k] != cb[k]:
            bad.append(f'{f.name}: {k} {ca[k]} -> {cb[k]}')
for k in tot_a:
    print(f'{k:20s} twin={tot_a[k]:7d} lowered={tot_b[k]:7d}')
print('differences:', len(bad))
for l in bad[:40]:
    print('  ', l)
sys.exit(1 if bad else 0)
