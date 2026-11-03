#!/usr/bin/env python3
"""T182 A/B runner (needs authorization): t181/ab/run_t181.py with the T182 exe and arms R, B, D.
  py -3 generated/analysis/t182/tools/make_runner_t182.py <exe sha256>
  py -3 generated/analysis/t182/ab/run_t182.py prepare r ; dryrun R x ; launch R r1"""
import re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t182.py <exe sha256 of build/motorstorm-t182>')
src = (ROOT / 'generated/analysis/t181/ab/run_t181.py').read_text(encoding='utf-8')
def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)
sub("'motorstorm-t181'", "'motorstorm-t182'")
sub(re.search(r"PIN = '[0-9a-f]{64}'", src).group(0), f"PIN = '{pin}'")
sub("f't181-{arm}{tag}'", "f't182-{arm}{tag}'")
sub("NO_NAV = ('S', 'T')", "ARMS = {'R': ARMS['R'], 'B': ARMS['B'], 'D': ('r', {**ARMS['B'][1], 'RSX_VP_DIRECT': '1'})}\nNO_NAV = ()")
sub("        for a in 'BWFMXVST':", "        for a in 'BD':")
sub("MAX_LAUNCHES = 10", "MAX_LAUNCHES = 3")
sub("ARM = 'A'\n", "ARM = 'R'\n")
sub("env['A']", "env['A']") if False else None
src = src.replace("env['A']", "env['R']").replace("'A vs", "'R vs").replace("f'A vs", "f'R vs")
out = HERE.parent / 'ab'; out.mkdir(exist_ok=True)
(out / 'cpath_sites.cfg').write_text((ROOT / 'generated/analysis/t181/ab/cpath_sites.cfg').read_text(encoding='utf-8'), encoding='utf-8')
(out / 'run_t182.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t182.py')
