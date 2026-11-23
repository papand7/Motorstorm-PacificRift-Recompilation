"""MSPR_CAM_SPRING (otherport item 4b): hooks in the ppucc2 lift (D:/motorstorm/ppucc2/ppu-v100-ppucc2) for
port-vkgame/main.cpp's chase-camera spring cadence. The originals are never modified: the three TUs are
copied to a staging directory and patched there; ot_link.py --ppu-override compiles the copies with the
original TUs' command lines.
  func_008CF1C0 entry (ppu_recomp_004.cpp): mspr_frame_step_note(f1)   the game's per-frame step
  func_0037FB68 entry (ppu_recomp_009.cpp): if (mspr_cam_spring_skip(r3)) return;
  func_0037FB64 entry (ppu_recomp_001.cpp, the alias one nop earlier): the same
Returning at entry is the function not running: it has not touched the stack yet, its callers overwrite
r3/r4/f1 after the call and keep nothing in volatile registers across it (checked at both call sites,
0x00380CBC and 0x00380D9C). Idempotent; every match count is asserted.
usage: py -3 spring_patch_ppucc.py [staging dir]"""
import hashlib, pathlib, shutil, sys

SRC = pathlib.Path('D:/motorstorm/ppucc2/ppu-v100-ppucc2')
ST = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path('D:/motorstorm/otherport-ppu')
DECL = ('extern "C" void mspr_frame_step_note(double dt); extern "C" int mspr_cam_spring_skip(uint64_t cam);'
        '   /* port main.cpp: MSPR_CAM_SPRING */')
EDITS = [
    ('ppu_recomp_004.cpp', 'void func_008CF1C0(ppu_context* ctx) { PPU_TR_ENTER(ctx, 0x008CF1C0u);',
     ' mspr_frame_step_note(ctx->fpr[1]);   /* MSPR_CAM_SPRING: frame step */'),
    ('ppu_recomp_009.cpp', 'void func_0037FB68(ppu_context* ctx) { PPU_TR_ENTER(ctx, 0x0037FB68u);',
     ' if (mspr_cam_spring_skip(ctx->gpr[3])) return;   /* MSPR_CAM_SPRING: chase springs at 30 Hz */'),
    ('ppu_recomp_001.cpp', 'void func_0037FB64(ppu_context* ctx) { PPU_TR_ENTER(ctx, 0x0037FB64u);',
     ' if (mspr_cam_spring_skip(ctx->gpr[3])) return;   /* MSPR_CAM_SPRING: chase springs at 30 Hz */'),
]

ST.mkdir(parents=True, exist_ok=True)
for name, head, add in EDITS:
    src, dst = SRC / name, ST / name
    if not dst.exists():
        shutil.copyfile(src, dst)
    b = dst.read_bytes().decode('latin-1')
    n_new = b.count(head + add)
    n_old = sum(b.count(head + eol) for eol in ('\r\n', '\n'))
    assert n_new + n_old == 1, (name, n_old, n_new)
    if n_old:
        b = b.replace(head, head + add, 1)
    lines = b.split('\n')
    if DECL not in '\n'.join(lines[1:5]):
        assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
        lines.insert(2, DECL + ('\r' if lines[1].endswith('\r') else ''))
        b = '\n'.join(lines)
    dst.write_bytes(b.encode('latin-1'))
    print(f'{name}: {"patched" if n_old else "already patched"} -> {dst} sha256 {hashlib.sha256(b.encode("latin-1")).hexdigest()[:16]}')
