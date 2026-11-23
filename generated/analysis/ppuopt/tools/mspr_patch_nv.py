"""Private (ppuopt) copy of launcher/pipeline/mspr_patch_lifted.py for a --nv-locals lift."""
"""MSPR_PATCH: route the four community code patches (60fps, vfps, drs, mblur) for MotorStorm: Pacific Rift BCUS98155 01.00
(authors illusion, ZEROx; the patch set is the community's, not a decryption input) through
mspr_patch_on(bit) in the lifted staging tree, so each is off unless MSPR_PATCH names it
(port-vkgame/main.cpp). Every lifted copy of a patched instruction is changed, and only those:
the edits are anchored to their function (and block label) and their counts are asserted.

  60fps  0x00435D1C  stw r4,0x18(r9) -> nop      (func_00435D18, and the linear copies in
                                                   func_00435B50 and func_00435D08)
  vfps   0x00435F9C  lwz r6,0x1C(r9) -> li r6,1  (func_00435F28)
  drs    0x00360590  lbz r3,4(r10)   -> li r3,0  (func_003603B8, block 0x0036058C, 2nd word)
  mblur  0x0035FDEC  lbz r3,0x18(r10) -> li r3,0 (func_0035FC18, block 0x0035FDEC, 1st word)

Idempotent. A hard-linked file is copied first, so the trees sharing it (ppu-hooked-staging)
keep their bytes. Usage: py -3 mspr_patch_lifted.py [staging dir]"""
import os
import pathlib
import re
import shutil
import sys

# (launcher copy of generated/analysis/vksync/tools/mspr_patch_lifted.py: the staging folder is an argument)
if len(sys.argv) < 2:
    sys.exit('usage: mspr_patch_lifted.py <lifted staging folder>')
ST = pathlib.Path(sys.argv[1])
DECL = 'extern "C" int mspr_patch_on(uint32_t bit);   /* port main.cpp: MSPR_PATCH */'
DECL_AUDIO = 'extern "C" int mspr_audio_kick(ppu_context* ctx);   /* port audio_thread.cpp */'

# (file, functions, (label, nth line after it) or None, old, new, expected count)
EDITS = [
    ('ppu_recomp_009.cpp', {'func_00435B50', 'func_00435D08', 'func_00435D18'}, None,
     'vm_write32(ctx->gpr[9] + 0x18, ctx->gpr[4]);',
     'if (!mspr_patch_on(1u)) vm_write32(ctx->gpr[9] + 0x18, ctx->gpr[4]);   /* 0x00435D1C; MSPR_PATCH=60fps: nop */', 3),
    ('ppu_recomp_009.cpp', {'func_00435F28'}, None,
     'ctx->gpr[6] = vm_read32(ctx->gpr[9] + 0x1C);',
     'ctx->gpr[6] = mspr_patch_on(2u) ? 1u : vm_read32(ctx->gpr[9] + 0x1C);   /* 0x00435F9C; MSPR_PATCH=vfps: li r6,1 */', 1),
    ('ppu_recomp_001.cpp', {'func_003603B8'}, ('loc_0036058C', 2),
     'ctx->gpr[3] = vm_read8(ctx->gpr[10] + 0x4);',
     'ctx->gpr[3] = mspr_patch_on(4u) ? 0u : vm_read8(ctx->gpr[10] + 0x4);   /* 0x00360590; MSPR_PATCH=drs: li r3,0 */', 1),
    ('ppu_recomp_001.cpp', {'func_0035FC18'}, ('loc_0035FDEC', 1),
     'ctx->gpr[3] = vm_read8(ctx->gpr[10] + 0x18);',
     'ctx->gpr[3] = mspr_patch_on(8u) ? 0u : vm_read8(ctx->gpr[10] + 0x18);   /* 0x0035FDEC; MSPR_PATCH=mblur: li r3,0 */', 1),
]

# 1.03 (ppu-v103-staging): the same four instructions, byte-identical, moved
# (generated/analysis/v103/tools/find_sites_103.py; all in ppu_recomp_001.cpp).
EDITS_V103 = [
    ('ppu_recomp_001.cpp', {'func_00407B40'}, None,   # 1.03 lift: no linear copies
     'vm_write32(ctx->gpr[9] + 0x18, ctx->gpr[4]);',
     'if (!mspr_patch_on(1u)) vm_write32(ctx->gpr[9] + 0x18, ctx->gpr[4]);   /* 1.03 0x00407B44; MSPR_PATCH=60fps: nop */', 1),
    ('ppu_recomp_001.cpp', {'func_00407D18'}, None,
     'ctx->gpr[6] = vm_read32(ctx->gpr[9] + 0x1C);',
     'ctx->gpr[6] = mspr_patch_on(2u) ? 1u : vm_read32(ctx->gpr[9] + 0x1C);   /* 1.03 0x00407D8C; MSPR_PATCH=vfps: li r6,1 */', 1),
    ('ppu_recomp_001.cpp', {'func_00347658'}, ('loc_0034782C', 2),
     'ctx->gpr[3] = vm_read8(ctx->gpr[10] + 0x4);',
     'ctx->gpr[3] = mspr_patch_on(4u) ? 0u : vm_read8(ctx->gpr[10] + 0x4);   /* 1.03 0x00347830; MSPR_PATCH=drs: li r3,0 */', 1),
    ('ppu_recomp_001.cpp', {'func_00346EB8'}, ('loc_0034708C', 1),
     'ctx->gpr[3] = vm_read8(ctx->gpr[10] + 0x18);',
     'ctx->gpr[3] = mspr_patch_on(8u) ? 0u : vm_read8(ctx->gpr[10] + 0x18);   /* 1.03 0x0034708C; MSPR_PATCH=mblur: li r3,0 */', 1),
    # audiothread (opt-in, bit 64): the audio update's virtual call from the frame function, handed to a worker
    # guest thread (port-vkgame/audio_thread.cpp). Its result is not used; the join is the frame's flip.
    ('ppu_recomp_000.cpp', {'func_00069C38'}, None,
     'ctx->lr = 0x0006A150; ps3_indirect_call(ctx); DRAIN_TRAMPOLINE(ctx); PPU_TR_RET(ctx, 0x0006A150u, 0x00000000u);',
     'if (mspr_patch_on(64u) && mspr_audio_kick(ctx)) { /* MSPR_PATCH=audiothread: 1.03 0x0006A14C */ } else { ctx->lr = 0x0006A150; ps3_indirect_call(ctx); DRAIN_TRAMPOLINE(ctx); PPU_TR_RET(ctx, 0x0006A150u, 0x00000000u); }', 1),
]
if 'v103' in ST.name:
    EDITS = EDITS_V103
# ppuopt: a --nv-locals lift (ps3recomp-opt): guest registers are the locals rN
SUBSTR = True
_nv = lambda t: re.sub(r'ctx->gpr\[(\d+)\]', r'r\1', t)
EDITS = [(f, fns, at, _nv(old), _nv(new), n) for f, fns, at, old, new, n in EDITS]
FUNC = re.compile(r'void (func_[0-9A-F]{8})\(ppu_context\* ctx\) \{')
LABEL = re.compile(r'(loc_[0-9A-F]{8}):')


def patch(name, edits):
    path = ST / name
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.mspr-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
        print(f'{name}: hard link replaced by a copy')
    lines = path.read_bytes().decode('latin-1').split('\n')
    done = [0] * len(edits)
    already = [0] * len(edits)
    fn, label, since = None, None, 0
    for i, raw in enumerate(lines):
        text = raw.rstrip('\r')
        m = FUNC.match(text)
        if m:
            fn, label, since = m.group(1), None, 0
            continue
        m = LABEL.match(text)
        if m:
            label, since = m.group(1), 0
            continue
        since += 1
        body = text.strip()
        for k, (_, fns, at, old, new, _n) in enumerate(edits):
            if fn not in fns or (at and (label != at[0] or since != at[1])):
                continue
            if body == new or (SUBSTR and new in body):
                already[k] += 1
            elif body == old or (SUBSTR and old in body):
                lines[i] = text.replace(old, new) + ('\r' if raw.endswith('\r') else '')
                done[k] += 1
    for k, e in enumerate(edits):
        got = done[k] + already[k]
        assert got == e[5], f'{name}: {e[4][-40:]} matched {got}, want {e[5]}'
    if any('mspr_audio_kick' in l for l in lines) and DECL_AUDIO not in lines[1] + lines[2] + lines[3]:
        eol_ = '\r' if lines[1].endswith('\r') else ''
        lines.insert(2, DECL_AUDIO + eol_)
    if DECL not in lines[1] + lines[2]:
        assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
        eol = '\r' if lines[1].endswith('\r') else ''
        lines.insert(2, DECL + eol)
    path.write_bytes('\n'.join(lines).encode('latin-1'))
    print(f'{name}: {sum(done)} lines patched, {sum(already)} already patched')


for f in sorted({e[0] for e in EDITS}):
    patch(f, [e for e in EDITS if e[0] == f])
