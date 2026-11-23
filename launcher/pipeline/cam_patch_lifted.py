"""MSPR_CAM: the camera-shake fix under MSPR_PATCH=vfps. The camera system scales its per-update deltas by a
rate in updates per second ([ctx+0x10], read by camerasystem::VehicleView 0x431200 and XYZSplineSmooth
0x432EB8). The game copies it each frame from a field set once (0x003764F0 from [obj+0xA58], 0x004295D0 from
[obj+0x3DC]); at the 30 fps lock it is 30, under vfps it stays 25 while the world steps the real frame time,
so camera and vehicle disagree every frame by an error that grows with speed (GLITCHES.md, Kk70; writers
found by PPU_WVAL in Kk114). This routes:
  World::Update's clamped world dt (fsel f31 at 0x002161C8, func_00216004/func_00216008) -> mspr_wdt_note()
  the two rate copies -> mspr_cam_rate(value), port-vkgame/main.cpp (1/dt under vfps, else unchanged).
  camerasystem::Shake's update (func_0042E3F0) -> mspr_cam_shake(active byte [this+0x28]): with MSPR_CAM_SHAKE=0
    an active shake returns at entry, as the game's own inactive path does (restore, no result); it also logs
    how often the shake is active. Its two result stores (camera vectors at [r4], [r4+0x10/0x20]) go through
    mspr_cam_shake_st16(), which blends old + MSPR_CAM_SHAKE * (shaken - old).
Idempotent; the counts are asserted. Usage: py -3 cam_patch_lifted.py [staging dir]"""
import os
import pathlib
import re
import shutil
import sys

# (launcher copy of generated/analysis/vksync/tools/cam_patch_lifted.py: the staging folder is an argument)
if len(sys.argv) < 2:
    sys.exit('usage: cam_patch_lifted.py <lifted staging folder>')
ST = pathlib.Path(sys.argv[1])
DECL = ('extern "C" void mspr_wdt_note(double dt); extern "C" float mspr_cam_rate(float v); '
        'extern "C" int mspr_cam_shake(uint32_t active); extern "C" void mspr_cam_shake_st16(uint64_t ea, const void* src);'
        '   /* port main.cpp: MSPR_CAM */')

FSEL = 'ctx->fpr[31] = (ctx->fpr[13] >= 0.0) ? ctx->fpr[0] : ctx->fpr[31];'
FSEL_NEW = FSEL + ' mspr_wdt_note(ctx->fpr[31]);   /* 0x002161C8 world dt; MSPR_CAM */'


def rate(base, addr):
    old = (f'{{ float ftmp = (float)ctx->fpr[13]; uint32_t tmp; memcpy(&tmp, &ftmp, 4); '
           f'vm_write32(ctx->gpr[{base}] + 0x10, tmp); }}')
    new = (f'{{ float ftmp = mspr_cam_rate((float)ctx->fpr[13]); uint32_t tmp; memcpy(&tmp, &ftmp, 4); '
           f'vm_write32(ctx->gpr[{base}] + 0x10, tmp); }}   /* {addr} camera rate; MSPR_CAM */')
    return old, new


SHAKE = 'void func_0042E3F0(ppu_context* ctx) { PPU_TR_ENTER(ctx, 0x0042E3F0u);'
SHAKE_NEW = SHAKE + ' if (mspr_cam_shake(vm_read8(ctx->gpr[3] + 0x28))) return;   /* MSPR_CAM_SHAKE */'

def st16(ea, vr, addr):
    old = f'{{ uint64_t ea = ({ea}) & ~0xFULL; vm_raw_st16(ea, &ctx->vr[{vr}]); }}'
    new = f'{{ uint64_t ea = ({ea}) & ~0xFULL; mspr_cam_shake_st16(ea, &ctx->vr[{vr}]); }}   /* {addr} shaken camera; MSPR_CAM_SHAKE */'
    return old, new


# (file, function, old, new, expected count)
EDITS = [
    ('ppu_recomp_001.cpp', 'func_0042E3F0', *st16('ctx->gpr[20]', 28, '0x0042EB54'), 1),
    ('ppu_recomp_001.cpp', 'func_0042E3F0', *st16('(ctx->gpr[23] + ctx->gpr[20])', 26, '0x0042EB5C'), 1),
    ('ppu_recomp_001.cpp', 'func_0042E3F0', *st16('ctx->gpr[20]', 27, '0x0042F330'), 1),
    ('ppu_recomp_001.cpp', 'func_0042E3F0', *st16('(ctx->gpr[23] + ctx->gpr[20])', 25, '0x0042F340'), 1),
    ('ppu_recomp_000.cpp', 'func_00216004', FSEL, FSEL_NEW, 1),
    ('ppu_recomp_009.cpp', 'func_00216008', FSEL, FSEL_NEW, 1),
    ('ppu_recomp_001.cpp', 'func_00376394', *rate(31, '0x003764F0'), 2),
    ('ppu_recomp_009.cpp', 'func_00376398', *rate(31, '0x003764F0'), 2),
    ('ppu_recomp_001.cpp', 'func_00429128', *rate(30, '0x004295D0'), 1),
]

FUNC = re.compile(r'void (func_[0-9A-F]{8})\(ppu_context\* ctx\) \{')


def patch(name, edits):
    path = ST / name
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.cam-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
        print(f'{name}: hard link replaced by a copy')
    lines = path.read_bytes().decode('latin-1').split('\n')
    done = [0] * len(edits)
    already = [0] * len(edits)
    fn = None
    for i, raw in enumerate(lines):
        text = raw.rstrip('\r')
        m = FUNC.match(text)
        if m:
            fn = m.group(1)
            continue
        body = text.strip()
        for k, (_, f, old, new, _n) in enumerate(edits):
            if fn != f:
                continue
            if body == new:
                already[k] += 1
            elif body == old:
                lines[i] = text.replace(old, new) + ('\r' if raw.endswith('\r') else '')
                done[k] += 1
    for k, e in enumerate(edits):
        got = done[k] + already[k]
        assert got == e[4], f'{name} {e[1]}: matched {got}, want {e[4]}'
    if DECL not in '\n'.join(lines[1:5]):
        assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
        eol = '\r' if lines[1].endswith('\r') else ''
        lines.insert(2, DECL + eol)
    path.write_bytes('\n'.join(lines).encode('latin-1'))
    print(f'{name}: {sum(done)} lines patched, {sum(already)} already patched')


for f in sorted({e[0] for e in EDITS}):
    patch(f, [e for e in EDITS if e[0] == f])

# The Shake entry is the function's own first line, so it is matched outside the per-function scan.
path = ST / 'ppu_recomp_001.cpp'
b = path.read_bytes().decode('latin-1')
n_old, n_new = b.count(SHAKE + '\r\n') + b.count(SHAKE + '\n'), b.count(SHAKE_NEW)
assert n_old + n_new == 1, (n_old, n_new)
if n_old:
    b = b.replace(SHAKE, SHAKE_NEW, 1)
    path.write_bytes(b.encode('latin-1'))
print('ppu_recomp_001.cpp: Shake entry', 'patched' if n_old else 'already patched')
