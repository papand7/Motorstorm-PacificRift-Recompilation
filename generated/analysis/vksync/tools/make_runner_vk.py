#!/usr/bin/env python3
"""Vulkan game A/B runner: t190/ab/run_t190.py with the vkgame exe and two arms.
  P  control: T190 arm P exactly (D3D12, the default backend).
  B  Vulkan:  P + RSX_BACKEND=vulkan, PS3RECOMP_VK_GUEST_PROGRAMS=1 (engine path), PS3RECOMP_VK_WINDOW=1, RSX_VK_STATS=1.
Same exe for both (built with PS3RECOMP_RSX_VULKAN=ON). Cap 2 launches, order Pp1 then Bb1, no retries.
  py -3 generated/analysis/vksync/tools/make_runner_vk.py <exe sha256 of build/motorstorm-vkgame>
  py -3 generated/analysis/vksync/ab/run_vk.py prepare r ; envcheck ; dryrun P p1 ; launch P p1"""
import re, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_vk.py <exe sha256 of build/motorstorm-vkgame>')
T190 = ROOT / 'generated/analysis/t190/ab'
src = (T190 / 'run_t190.py').read_text(encoding='utf-8')
def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)
sub("'motorstorm-t190'", "'motorstorm-vkgame'")
sub(re.search(r"PIN = '[0-9a-f]{64}'", src).group(0), f"PIN = '{pin}'")
sub("f't190-{arm}{tag}'", "f'vk-{arm}{tag}'")
sub("'B': ('r', {**ARMS['P'][1], 'PS3_VM_STORE_INLINE': '1'})}   # T190: the one switch",
    "'B': ('r', {**ARMS['P'][1], 'RSX_BACKEND': 'vulkan', 'PS3RECOMP_VK_GUEST_PROGRAMS': '1', "
    "'PS3RECOMP_VK_WINDOW': '1', 'RSX_VK_STATS': '1'})}   # Vulkan: the one switch")
sub("ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2']   # T190: the authorized sequence",
    "ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2', 'Bb3', 'Pp3', 'Bb4']   # Pp1/Bb1: first exe (Bb1 failed the intro check: no Vulkan frame reports); "
    "Pp2/Bb2: frame-report fix (Bb2 hit GcKernel::Present() Timeout); Bb3: timed-wait logging + [rsx-hb]; Pp3/Bb4: clean pair, periodic [vk-stats]")
sub("MAX_LAUNCHES = 4", "MAX_LAUNCHES = 7")
out = HERE.parent / 'ab'; out.mkdir(exist_ok=True)
(out / 'cpath_sites.cfg').write_text((T190 / 'cpath_sites.cfg').read_text(encoding='utf-8'), encoding='utf-8')
if not (out / 'shader_cache').exists():
    shutil.copytree(T190 / 'shader_cache', out / 'shader_cache')
(out / 'run_vk.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_vk.py')
