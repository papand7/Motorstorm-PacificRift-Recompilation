#!/usr/bin/env python3
"""T183 A/B runner (needs authorization): t182/ab/run_t182.py with the T183 exe and arms S, B, C.
S = D-free T182 B + diagnostics, not timed. B = T182 B. C = B + PS3_ICALL_FAST, PS3_SPU_TASK_POOL, PS3_SPU_TASK_QUIET.
All arms share a shader cache already warmed by T182 B and D.
  py -3 generated/analysis/t183/tools/make_runner_t183.py <exe sha256>
  py -3 generated/analysis/t183/ab/run_t183.py prepare r ; envcheck ; dryrun S x ; launch S s1"""
import re, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t183.py <exe sha256 of build/motorstorm-t183>')
src = (ROOT / 'generated/analysis/t182/ab/run_t182.py').read_text(encoding='utf-8')
def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)
sub("'motorstorm-t182'", "'motorstorm-t183'")
sub(re.search(r"PIN = '[0-9a-f]{64}'", src).group(0), f"PIN = '{pin}'")
sub("f't182-{arm}{tag}'", "f't183-{arm}{tag}'")
sub("ARMS = {'R': ARMS['R'], 'B': ARMS['B'], 'D': ('r', {**ARMS['B'][1], 'RSX_VP_DIRECT': '1'})}",
    "ARMS = {'B': ARMS['B'], 'C': ('r', {**ARMS['B'][1], 'PS3_ICALL_FAST': '1', 'PS3_SPU_TASK_POOL': '1', 'PS3_SPU_TASK_QUIET': '1'}),\n"
    "        'S': ('r', {**ARMS['B'][1], 'PS3_SAMPLE': '2', 'PS3_SAMPLE_MAIN': '1', 'PS3_SAMPLE_TOP': '25', 'PS3_SPU_TASK_STATS': '1000', "
    "'SPURS_BUSY_MS': '1000', 'PS3_SC_WAIT_MS': '1000', 'PS3_HLE_WAIT_MS': '1000'})}")
sub("MAX_LAUNCHES = 3", "MAX_LAUNCHES = 5")
sub("        for a in 'BD':", "        for a in 'CS':")
sub("ARM = 'R'\n", "ARM = 'B'\n")
src = src.replace("env['R']", "env['B']").replace("'R vs", "'B vs").replace("f'R vs", "f'B vs")
out = HERE.parent / 'ab'; out.mkdir(exist_ok=True)
(out / 'cpath_sites.cfg').write_text((ROOT / 'generated/analysis/t182/ab/cpath_sites.cfg').read_text(encoding='utf-8'), encoding='utf-8')
if not (out / 'shader_cache').exists():
    shutil.copytree(ROOT / 'generated/analysis/t182/ab/shader_cache', out / 'shader_cache')
(out / 'run_t183.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t183.py')
