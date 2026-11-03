#!/usr/bin/env python3
"""T187 A/B runner (launches need authorization): t183/ab/run_t183.py with the T187 exe and two arms.
P = T184 arm P unchanged (arm S + PS3_SPU_TASK_POOL=1), switch off. F = P + PS3_SPU_MFC_FAST=1. Same exe.
Shader cache: a copy of t183/ab/shader_cache, already warm from T183/T184. Launch cap 4 (P F P F).
  py -3 generated/analysis/t187/tools/make_runner_t187.py <exe sha256 of build/motorstorm-t187>
  py -3 generated/analysis/t187/ab/run_t187.py prepare r ; envcheck ; dryrun P x ; launch P p1 ; launch F f1 ..."""
import re, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t187.py <exe sha256 of build/motorstorm-t187>')
src = (ROOT / 'generated/analysis/t183/ab/run_t183.py').read_text(encoding='utf-8')
def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)
sub("'motorstorm-t183'", "'motorstorm-t187'")
sub(re.search(r"PIN = '[0-9a-f]{64}'", src).group(0), f"PIN = '{pin}'")
sub("f't183-{arm}{tag}'", "f't187-{arm}{tag}'")
sub("ARMS['P'] = ('r', {**ARMS['S'][1], 'PS3_SPU_TASK_POOL': '1'})",
    "ARMS['P'] = ('r', {**ARMS['S'][1], 'PS3_SPU_TASK_POOL': '1'})\n"
    "ARMS['F'] = ('r', {**ARMS['P'][1], 'PS3_SPU_MFC_FAST': '1'})   # T187: arm P + the switch, nothing else")
sub("MAX_LAUNCHES = 5", "MAX_LAUNCHES = 4")
sub("        for a in 'CSP':", "        for a in 'PF':")
out = HERE.parent / 'ab'; out.mkdir(exist_ok=True)
(out / 'cpath_sites.cfg').write_text((ROOT / 'generated/analysis/t183/ab/cpath_sites.cfg').read_text(encoding='utf-8'), encoding='utf-8')
if not (out / 'shader_cache').exists():
    shutil.copytree(ROOT / 'generated/analysis/t183/ab/shader_cache', out / 'shader_cache')
(out / 'run_t187.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t187.py')
