#!/usr/bin/env python3
"""T190 runner: t183/ab/run_t183.py with the T190 exe (build/motorstorm-t190) and two arms.
  P  control:   T184 arm P exactly (T183 arm S + PS3_SPU_TASK_POOL=1).
  B  optimized: P + PS3_VM_STORE_INLINE=1. Nothing else differs (envcheck).
Same exe for both (built with MSPR_PPU_INLINE_STORES=ON). Cap 4 launches, fixed order Pp1 Bb1 Pp2 Bb2,
no retries (a launch tag is consumed when it starts). Godot is a refused process here (T190 brief).
  py -3 generated/analysis/t190/tools/make_runner_t190.py <exe sha256>
  py -3 generated/analysis/t190/ab/run_t190.py prepare r ; envcheck ; dryrun P p1 ; launch P p1"""
import re, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t190.py <exe sha256 of build/motorstorm-t190>')
src = (ROOT / 'generated/analysis/t183/ab/run_t183.py').read_text(encoding='utf-8')
def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)
sub("'motorstorm-t183'", "'motorstorm-t190'")
sub(re.search(r"PIN = '[0-9a-f]{64}'", src).group(0), f"PIN = '{pin}'")
sub("f't183-{arm}{tag}'", "f't190-{arm}{tag}'")
sub("ARMS['P'] = ('r', {**ARMS['S'][1], 'PS3_SPU_TASK_POOL': '1'})   # T184: arm S + the task pool, nothing else\n",
    "ARMS['P'] = ('r', {**ARMS['S'][1], 'PS3_SPU_TASK_POOL': '1'})   # T184: arm S + the task pool, nothing else\n"
    "ARMS = {'P': ARMS['P'], 'B': ('r', {**ARMS['P'][1], 'PS3_VM_STORE_INLINE': '1'})}   # T190: the one switch\n"
    "ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2']   # T190: the authorized sequence\n")
sub("MAX_LAUNCHES = 5", "MAX_LAUNCHES = 4")
sub("CONFLICTS = ('ollama',", "CONFLICTS = ('godot', 'ollama',")
sub("OPEN_OK = ('leoffice', 'godot')", "OPEN_OK = ('leoffice',)")
sub("    if any(json.loads(l)['tag'] == f'{REQ}' for l in used):\n",
    "    if len(used) < len(ORDER) and REQ != ORDER[len(used)]:\n"
    "        fails.append(f'out of order: next authorized launch is {ORDER[len(used)]}, not {REQ}')\n"
    "    if any(json.loads(l)['tag'] == f'{REQ}' for l in used):\n")
sub("        for a in 'CSP':", "        for a in 'P':")
out = HERE.parent / 'ab'; out.mkdir(exist_ok=True)
(out / 'cpath_sites.cfg').write_text((ROOT / 'generated/analysis/t183/ab/cpath_sites.cfg').read_text(encoding='utf-8'), encoding='utf-8')
if not (out / 'shader_cache').exists():
    shutil.copytree(ROOT / 'generated/analysis/t185/ab/shader_cache', out / 'shader_cache')
(out / 'run_t190.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t190.py')
