"""MSPR_DEBUG_FLY pause: the game's simulation step is held while the debug free-fly camera is on (F3).

func_008CF1C0 (1.00, ppu_recomp_004.cpp) is the frame's simulation step. It receives the step in f1 and
passes it on: its body runs only when f1 is above the constant at [r2+0x3A10] (cr bit GT after the
fcmpu at the top), and the body calls the game clock (func_0031BA20), the world update (func_00313850)
and the per-frame object updates. Setting f1 to 0 at entry therefore skips the step while fly mode is on,
and the frame function still returns normally, so the frame keeps drawing and the view keeps updating.
The hook is the function's first statement after PPU_TR_ENTER, before f1 is read:

  ctx->fpr[1] = mspr_fly_sim_step(ctx->fpr[1]);   /* MSPR_DEBUG_FLY: 0 while fly mode is on */

mspr_fly_sim_step (port-vkgame/main.cpp) returns f1 unchanged unless MSPR_DEBUG_FLY=1 and F3 has turned the
fly camera on. Nothing else is held: the step is the game's own clock, so when fly mode turns off the next
step is the game's own dt and the sim continues from where it stopped (no catch-up, no drift; the host test
is port-vkgame/tests/test_fly_pause.c).

The function's other entry points are not touched. The anchor is asserted: the hook is inserted once, and a
lifted tree whose anchor line differs makes this script fail (the build must not run on an unpatched site).
Idempotent. A hard-linked file is copied first, as in the other patch scripts.

usage: py -3 fly_pause_patch_lifted.py <lifted staging folder>"""
import os
import pathlib
import shutil
import sys

if len(sys.argv) < 2:
    sys.exit('usage: fly_pause_patch_lifted.py <lifted staging folder>')
ST = pathlib.Path(sys.argv[1])
NAME = 'ppu_recomp_004.cpp'
DECL = 'extern "C" double mspr_fly_sim_step(double dt);   /* port main.cpp: MSPR_DEBUG_FLY */'
HEAD = 'void func_008CF1C0(ppu_context* ctx) { PPU_TR_ENTER(ctx, 0x008CF1C0u);'
HOOK = ' ctx->fpr[1] = mspr_fly_sim_step(ctx->fpr[1]);   /* MSPR_DEBUG_FLY: 0 while fly mode is on */'

path = ST / NAME
if not path.exists():
    sys.exit(f'fly pause: {path} not found (the lifted staging folder is wrong)')
if os.stat(path).st_nlink > 1:
    tmp = path.with_suffix('.cpp.fly-tmp')
    shutil.copyfile(path, tmp)
    os.replace(tmp, path)
    print(f'{NAME}: hard link replaced by a copy')

raw = path.read_bytes().decode('latin-1')
n_head = raw.count(HEAD)
assert n_head == 1, f'{NAME}: func_008CF1C0 entry matched {n_head} times, want 1'
if HOOK in raw:
    n_hook = raw.count(HOOK)
    assert n_hook == 1, f'{NAME}: fly pause hook present {n_hook} times, want 1'
    print(f'{NAME}: already patched')
else:
    raw = raw.replace(HEAD, HEAD + HOOK, 1)
    lines = raw.split('\n')
    assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
    if 'mspr_fly_sim_step' not in lines[1] + lines[2] + lines[3]:
        eol = '\r' if lines[1].endswith('\r') else ''
        lines.insert(2, DECL + eol)
    raw = '\n'.join(lines)
    path.write_bytes(raw.encode('latin-1'))
    print(f'{NAME}: fly pause hook applied at func_008CF1C0 entry')
assert raw.count(HOOK) == 1 and raw.count(DECL) == 1, f'{NAME}: hook or declaration not in place'
