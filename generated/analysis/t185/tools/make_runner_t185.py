#!/usr/bin/env python3
"""T185 runner (prepared, NOT run without authorization): t183/ab/run_t183.py with the T185 exe and three arms.
All arms start from T184 arm P (= T183 arm S + PS3_SPU_TASK_POOL=1) and differ only in T185 instrumentation:
  Q  diagnostic (the next experiment): P + PS3_SPU_CREATE_PROFILE=1 + PS3_SPU_LLAR_PROFILE=1 + phase-tagged
     PPU sampling (PS3_SAMPLE=2, MAIN, TOP=40, PS3_SAMPLE_PHASES). Logging NOT quiet, so the create profile's
     `log` stage measures today's logging cost.
  N  overhead control: P without the PS3_SAMPLE* keys (on the T185 exe the sampler is live; on T183 it never ran),
     no T185 flags. Frame time here vs Q bounds the instrumentation overhead; vs T184 P, the exe change.
  L  logging A/B: N + PS3_SPU_CREATE_PROFILE=1 + PS3_SPU_TASK_QUIET=1. The create profile against Q's says what
     quiet removes from each call; frame time against N (with the profile's own cost known from Q) what it buys.
One arm per invocation, cap 3 launches; each launch needs its own authorization.
  py -3 generated/analysis/t185/tools/make_runner_t185.py <exe sha256>
  py -3 generated/analysis/t185/ab/run_t185.py prepare r ; envcheck ; dryrun Q x"""
import re, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t185.py <exe sha256 of build/motorstorm-t185>')
src = (ROOT / 'generated/analysis/t183/ab/run_t183.py').read_text(encoding='utf-8')
def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)
sub("'motorstorm-t183'", "'motorstorm-t185'")
sub(re.search(r"PIN = '[0-9a-f]{64}'", src).group(0), f"PIN = '{pin}'")
sub("f't183-{arm}{tag}'", "f't185-{arm}{tag}'")
sub("ARMS['P'] = ('r', {**ARMS['S'][1], 'PS3_SPU_TASK_POOL': '1'})   # T184: arm S + the task pool, nothing else\n",
    "ARMS['P'] = ('r', {**ARMS['S'][1], 'PS3_SPU_TASK_POOL': '1'})   # T184: arm S + the task pool, nothing else\n"
    "_PHASES = '72E1E0:pre,30B710:havok:post,50D868:emit,50C818:spin:tail'   # T183 frame phases; all are PT fn= sites\n"
    "_NOSAMP = {k: v for k, v in ARMS['P'][1].items() if not k.startswith('PS3_SAMPLE')}\n"
    "ARMS = {'Q': ('r', {**ARMS['P'][1], 'PS3_SAMPLE_TOP': '40', 'PS3_SAMPLE_PHASES': _PHASES,\n"
    "                    'PS3_SPU_CREATE_PROFILE': '1', 'PS3_SPU_LLAR_PROFILE': '1'}),\n"
    "        'N': ('r', dict(_NOSAMP)),\n"
    "        'L': ('r', {**_NOSAMP, 'PS3_SPU_CREATE_PROFILE': '1', 'PS3_SPU_TASK_QUIET': '1'}),\n"
    "        'B': ARMS['B']}\n")
sub("MAX_LAUNCHES = 5", "MAX_LAUNCHES = 3")
sub("        for a in 'CSP':", "        for a in 'QNL':")
out = HERE.parent / 'ab'; out.mkdir(exist_ok=True)
(out / 'cpath_sites.cfg').write_text((ROOT / 'generated/analysis/t183/ab/cpath_sites.cfg').read_text(encoding='utf-8'), encoding='utf-8')
if not (out / 'shader_cache').exists():
    shutil.copytree(ROOT / 'generated/analysis/t183/ab/shader_cache', out / 'shader_cache')
(out / 'run_t185.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t185.py')
