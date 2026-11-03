#!/usr/bin/env python3
"""T188: build the four offline code-generation variants of one private lift TU.

  make_variants.py <NNN> [--fpr0]

  v_out/  staging header (stores out of line):  base.cpp, promo.cpp
  v_inl/  staging header with T152's page-gate/inline-store block (make_t152_lift.py's
          verified substitution), compiled with -DPPU_INLINE_STORES:  base.cpp, promo.cpp
promo.cpp = ps3recomp-t188/tools/ppu_regpromo.py applied to base.cpp (v_inl: stores inline, so
clean locals are not dropped at stores). Private: lifted code, never committed."""
import sys
from pathlib import Path
T = Path(__file__).resolve().parents[1]
M = T.parents[2]
sys.path.insert(0, str(M / 'ps3recomp-t188/tools'))
sys.path.insert(0, str(M / 'generated/analysis/t152/tools'))
import ppu_regpromo as rp
import make_t152_lift as m152

nnn = sys.argv[1]
STG = M / 'generated/ppu-t173-staging'
src = (STG / f'ppu_recomp_{nnn}.cpp').read_text(encoding='latin-1')
hdr = (STG / 'ppu_recomp.h').read_bytes().decode('latin-1')
t152 = (T / 'scratch/lifter_t152.py').read_text(encoding='utf-8')
a = t152.index('/* T152 page gates: begin */')
b = t152.index('/* T152 page gates: end */') + len('/* T152 page gates: end */')
h = hdr.replace('\r\n', '\n')
anchor = 'extern uint32_t ppu_hle_inject_base;\n'
i = h.index(anchor) + len(anchor)
assert h.count(m152.OLD) == 1 and h[i:].startswith(m152.OLD), 'gate block not where expected'
h_inl = h[:i] + t152[a:b] + '\n' + h[i + len(m152.OLD):]
fpr = '--fpr0' not in sys.argv
for d, header, inval in (('v_out', h, True), ('v_inl', h_inl, False)):
    out = T / 'scratch' / d
    out.mkdir(parents=True, exist_ok=True)
    (out / 'ppu_recomp.h').write_text(header, encoding='latin-1', newline='\n')
    (out / f'base_{nnn}.cpp').write_text(src, encoding='latin-1', newline='\n')
    st = {}
    p = rp.promote_source(src, st, invalidate_clean=inval, promote_fpr=fpr)
    (out / f'promo_{nnn}.cpp').write_text(p, encoding='latin-1', newline='\n')
    print(d, {k: v for k, v in st.items() if k != 'fallback'}, sum(st.get('fallback', {}).values()), 'unchanged')
