#!/usr/bin/env python3
"""drawcap runner: t194/ab/run_t194.py (T190 race route, frame dumps, console or RDP) with the drawcap exe
(build/motorstorm-drawcap, -DRSX_MAX_DRAWS=8192) and one arm:
  D  T190 arm P env exactly (default renderer, the user's washed-out/streaked race) + T194's frame dumps.
Cap 1 launch, no retries. Compare its frames with T194 Pp2 (2048-record batch, visual switches off) and check
stderr for '[VPVB] early replay ... records' (expected 0 with the larger batch).
  py -3 generated/analysis/drawcap/tools/make_runner_drawcap.py <exe sha256>
  py -3 generated/analysis/drawcap/ab/run_drawcap.py prepare r ; dryrun D d1 ; launch D d1"""
import re, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_drawcap.py <exe sha256 of build/motorstorm-drawcap>')
src = (ROOT / 'generated/analysis/t194/ab/run_t194.py').read_text(encoding='utf-8')
def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)
sub("'motorstorm-t194'", "'motorstorm-drawcap'")
sub(re.search(r"PIN = '[0-9a-f]{64}'", src).group(0), f"PIN = '{pin}'")
sub("f't194-{arm}{tag}'", "f'drawcap-{arm}{tag}'")
sub("ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2', 'Cc1', 'Ff1', 'Xx1', 'Zz1', 'Bb3', 'Bb4', 'Gg1', 'Kk1']",
    "ARMS = {'D': ('r', {k: v for k, v in ARMS['P'][1].items() if k not in _VOFF})}   # drawcap: T190 arm P env\n"
    "ORDER = ['Dd1', 'Dd2']   # Dd2: rerun after the s_fpm[MAX_DRAWS] fix")
sub("MAX_LAUNCHES = 12", "MAX_LAUNCHES = 2")
out = HERE.parent / 'ab'; out.mkdir(exist_ok=True)
for f in ('cpath_sites.cfg',):
    (out / f).write_text((ROOT / 'generated/analysis/t190/ab' / f).read_text(encoding='utf-8'), encoding='utf-8')
if not (out / 'shader_cache').exists():
    shutil.copytree(ROOT / 'generated/analysis/t190/ab/shader_cache', out / 'shader_cache')
(out / 'run_drawcap.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_drawcap.py')
