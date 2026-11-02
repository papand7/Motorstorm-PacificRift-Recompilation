#!/usr/bin/env python3
"""T178: generate ab/run_t178.py from t171/ab/run_t171.py, one substitution per change.

usage: py -3 make_runner_t178.py <exe sha256>
Arms: A = T171 arm B's set + the box diagnostics; B = A + TEX_NOCACHE=1. Preparing the runner launches nothing.
"""
import shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
T178 = HERE.parent
T171 = T178.parent / 't171' / 'ab'
src = (T171 / 'run_t171.py').read_text(encoding='utf-8')


def sub(old, new):
    global src
    if src.count(old) != 1:
        raise SystemExit(f'expected one match: {old!r}, got {src.count(old)}')
    src = src.replace(old, new)


sub("ROOT / 'build' / 'motorstorm-t171' /", "ROOT / 'build' / 'motorstorm-t178' /")
sub("PIN = '4450ea1fa8d31bcfd6f24ca9b6018459331dad96d6e4d14989b9511d6d12a8be'", f"PIN = '{sys.argv[1]}'")
sub("ARMS = {'A': ('t', {**BASE, 'RSX_SHADER_WINDOW': '0'}), 'B': ('t', {**BASE, 'RSX_SHADER_WINDOW': '1'})}",
    "# T178: unit 0 zeta, unit 1 box alpha, unit 11 colour; guest bytes of small textures; target after each box draw.\n"
    "BOX = {'RSX_SHADER_WINDOW': '1', 'RSXI_VP_CONSTS': '512', 'RSXI_UNITS': '803', 'RSXI_TEX_BYTES': '32', 'RSXI_SNAP_FP': '022C20C1'}\n"
    "ARMS = {'A': ('t', {**BASE, **BOX}), 'B': ('t', {**BASE, **BOX, 'TEX_NOCACHE': '1'})}")
sub("EXPECT = {'A': _E + '0', 'B': _E + '1'}", "# this tree's [visual] line ends at rt_reinterp\n"
    "_E = _E.replace(' shader_window=', '')\n"
    "EXPECT = {'A': _E, 'B': _E}")

ab = T178 / 'ab'
ab.mkdir(exist_ok=True)
(ab / 'run_t178.py').write_text(src, encoding='utf-8')
for name in ('cpath_sites.cfg', 'snapshot_manifest.json'):
    if (T171 / name).exists():
        shutil.copy2(T171 / name, ab / name)
print('wrote', ab / 'run_t178.py')
