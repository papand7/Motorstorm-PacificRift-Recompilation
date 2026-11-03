"""T136: static helper-use counts in lifted SPU sources (private).
  py -3 -I opfreq.py <spu_recomp.c | dir> ...   -> per-helper counts, top N"""
import re, sys
from collections import Counter
from pathlib import Path
tot = Counter(); n = 0
for a in sys.argv[1:]:
    p = Path(a)
    files = [p] if p.is_file() else list(p.rglob('spu_recomp.c'))
    for f in files:
        t = f.read_text(errors='replace')
        tot.update(re.findall(r'\b(spu_[a-z0-9_]+)\(', t))
        tot['<ctx->gpr assign>'] += len(re.findall(r'ctx->gpr\[\d+\] = ', t))
        tot['<trampoline return>'] += t.count('g_spu_trampoline_fn = ')
        n += 1
print(f'{n} file(s)')
for k, v in tot.most_common(): print(f'{v:8d} {k}')
