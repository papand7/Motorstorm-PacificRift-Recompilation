"""T136: static-mix cost estimate (HYPOTHESIS-grade: static counts, not dynamic). Weights each
helper's static count in the lifted images by its measured ns (logs/ops_median.md, plain set);
unmeasured helpers 0.3 ns; trampoline returns and brsl call sequences 5 ns (Bink chainbench)."""
import re, sys
from pathlib import Path
L = Path(__file__).resolve().parents[1] / 'logs'
cost = {}
for line in (L / 'ops_median.md').read_text().splitlines():
    p = [x.strip() for x in line.strip('|').split('|')]
    if len(p) == 5 and p[1] in ('plain', 'ls'):
        try: cost[p[0]] = (float(p[2]), float(p[3]))
        except ValueError: pass
alias = {'lqd': 'spu_ls_read128', 'stqd': 'spu_ls_write128'}
for name in sys.argv[1:]:
    counts = {}
    for line in (L / name).read_text().splitlines()[1:]:
        n, k = line.split(None, 1); counts[k.strip()] = int(n)
    # full list: re-run the counter without the top-60 cut
    base = new = 0.0; changed_b = changed_n = 0.0
    for k, n in counts.items():
        if k == '<ctx->gpr assign>': continue
        if k == '<trampoline return>': b = nn = 5.0
        elif k in ('spu_drain_call',): b = nn = 5.0
        else:
            op = k[4:]; op = {v: kk for kk, v in alias.items()}.get(k, op)
            b, nn = cost.get(op, (0.3, 0.3))
        base += n * b; new += n * nn
        if b != nn: changed_b += n * b; changed_n += n * nn
    print(f'{name}: static-weighted ns base {base:,.0f} new {new:,.0f} ({100*(base-new)/base:.1f}% less); '
          f'changed ops {100*changed_b/base:.1f}% of base')
