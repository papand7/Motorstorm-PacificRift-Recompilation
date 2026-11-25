"""Screens (settings.ini "screens", PS3RECOMP_VK_SPAN=2|3): Hor+ for a window over two or three monitors.

func_004302B4 (1.00, ppu_recomp_001.cpp; func_004302A8 sets two registers and branches to it) builds a lens's
frustum: each half-angle is the arc tangent of a film size times a constant over the focal length [lens+0xB0],
the width from [lens+0xB4], the height from [lens+0xB8], stored as the frustum vector at lens+0x70. The width is
loaded once, into f11, and multiplied right after:

  { uint32_t tmp = vm_read32(ctx->gpr[4] + 0x0); ... ctx->fpr[11] = ftmp; }     r4 = lens + 0xB4
  ctx->fpr[9] = ppu_fp_single(ppu_fmul(ctx->fpr[11], ctx->fpr[29]));

The hook goes between the two:

  ctx->fpr[11] = mspr_screens_film(ctx->fpr[11]);   /* Screens: Hor+ film width (port main.cpp) */

mspr_screens_film (port-vkgame/main.cpp) returns the value unchanged unless the backend opened a span window; then
it multiplies it by the window's aspect over 16:9, so tan(horizontal half-angle) grows by that factor and the
vertical field, the focal length and the lens memory stay as they are (a register, not the guest's memory: a lens
rebuilt again gets the same result).

The anchor pair is asserted inside func_004302B4 only: the hook is inserted once, and a lifted tree whose lines
differ makes this script fail. Idempotent. A hard-linked file is copied first, as in the other patch scripts.

usage: py -3 screens_patch_lifted.py <lifted staging folder>"""
import os
import pathlib
import shutil
import sys

if len(sys.argv) < 2:
    sys.exit('usage: screens_patch_lifted.py <lifted staging folder>')
ST = pathlib.Path(sys.argv[1])
NAME = 'ppu_recomp_001.cpp'
DECL = 'extern "C" double mspr_screens_film(double v);   /* port main.cpp: Screens (PS3RECOMP_VK_SPAN) */'
HEAD = 'void func_004302B4(ppu_context* ctx) { PPU_TR_ENTER(ctx, 0x004302B4u);'
LOAD = '{ uint32_t tmp = vm_read32(ctx->gpr[4] + 0x0); float ftmp; memcpy(&ftmp, &tmp, 4); ctx->fpr[11] = ftmp; }'
USE = 'ctx->fpr[9] = ppu_fp_single(ppu_fmul(ctx->fpr[11], ctx->fpr[29]));'
HOOK = 'ctx->fpr[11] = mspr_screens_film(ctx->fpr[11]);   /* Screens: Hor+ film width (port main.cpp) */'

path = ST / NAME
if not path.exists():
    sys.exit(f'screens: {path} not found (the lifted staging folder is wrong)')
raw = path.read_bytes().decode('latin-1')
n_head = raw.count(HEAD)
assert n_head == 1, f'{NAME}: func_004302B4 entry matched {n_head} times, want 1'
lines = raw.split('\n')
eol = '\r' if lines[0].endswith('\r') else ''
start = next(i for i, l in enumerate(lines) if HEAD in l)
end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith('void func_') or lines[i].startswith('}'))
body = range(start, end)
hooked = [i for i in body if lines[i].strip() == HOOK]
if hooked:
    assert len(hooked) == 1, f'{NAME}: Screens hook present {len(hooked)} times in func_004302B4, want 1'
    assert lines[hooked[0] - 1].strip() == LOAD and lines[hooked[0] + 1].strip() == USE, f'{NAME}: Screens hook out of place'
    print(f'{NAME}: already patched')
else:
    at = [i for i in body if lines[i].strip() == LOAD]
    assert len(at) == 1, f'{NAME}: film width load matched {len(at)} times in func_004302B4, want 1'
    assert lines[at[0] + 1].strip() == USE, f'{NAME}: the line after the film width load is not its multiply'
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.screens-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
        print(f'{NAME}: hard link replaced by a copy')
    indent = lines[at[0]][:len(lines[at[0]]) - len(lines[at[0]].lstrip())]
    lines.insert(at[0] + 1, indent + HOOK + eol)
    assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
    if not any('mspr_screens_film' in l for l in lines[1:6]):
        lines.insert(2, DECL + eol)
    raw = '\n'.join(lines)
    path.write_bytes(raw.encode('latin-1'))
    print(f'{NAME}: Screens hook applied in func_004302B4 (film width, f11)')
assert raw.count(HOOK) == 1 and raw.count(DECL) == 1, f'{NAME}: hook or declaration not in place'
