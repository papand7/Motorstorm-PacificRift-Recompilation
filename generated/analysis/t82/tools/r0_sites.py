#!/usr/bin/env python3
"""T82: every instruction that writes $r0 other than the standard epilogue reload, and the first
control transfer within the next 6 instructions (manual-link calls, computed returns).

  py -3 -I r0_sites.py <listing from dis.py>"""
import re, sys

L = [l.rstrip() for l in open(sys.argv[1])]
WR0 = re.compile(r'^\w+: \w{8}  (\w+) \$r0(,|$)')
XFER = re.compile(r'^\w+: \w{8}  (br|brz|brnz|brhz|brhnz|bra|bi|biz|binz|bisl|brsl|brasl)\b')
for i, l in enumerate(L):
    m = WR0.match(l)
    if not m or m.group(1) in ('stqd', 'stqx', 'stqr', 'stqa', 'wrch', 'brz', 'brnz', 'brhz', 'brhnz',
                               'biz', 'binz', 'bihz', 'bihnz', 'hbrr', 'hbr', 'bi', 'bisl'):
        continue
    nxt = next((c for c in L[i + 1:i + 7] if XFER.match(c)), '-')
    print(f'{l:52s} || {nxt}')
