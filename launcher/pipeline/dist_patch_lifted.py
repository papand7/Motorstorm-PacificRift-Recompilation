"""MSPR_DIST: route MotorStorm's draw, LOD and shadow distances through mspr_dist_f(kind, value) in the lifted
staging tree (port-vkgame/main.cpp), so each stays the game's value unless MSPR_SHADOW_RANGE, MSPR_CULL_SCALE,
MSPR_LOD_BIAS or MSPR_SHADOW_FADE is set. Sites (generated/analysis/distance/DISTANCE.md, static analysis):

  0 shadow range  0x006001AC  lis r3,0x4348 (200.0f) -> ShadowViewManagerImpl +0x74/+0x78  (func_006000F8)
  1 lodBias       0x0036196C  stfs -> group +0x0   (viewportquality.xml GroupSettings, func_00360DD4)
  2 cullThreshold 0x003619C8  stfs -> group +0xC
  3 shadowCull    0x003619F4  stfs -> group +0x10
  4 shadowFade    0x00361564  stfs -> GlobalConfig +0x3C (Shadows shadowFadeDistModifier)

Idempotent; the counts are asserted. Usage: py -3 dist_patch_lifted.py [staging dir]"""
import os
import pathlib
import re
import shutil
import sys

# (launcher copy of generated/analysis/vksync/tools/dist_patch_lifted.py: the staging folder is an argument)
if len(sys.argv) < 2:
    sys.exit('usage: dist_patch_lifted.py <lifted staging folder>')
ST = pathlib.Path(sys.argv[1])
DECL = 'extern "C" float mspr_dist_f(int kind, float v);   /* port main.cpp: MSPR_DIST */'


def st(fpr, base, off, kind, addr, name):
    old = (f'{{ float ftmp = (float)ctx->fpr[{fpr}]; uint32_t tmp; memcpy(&tmp, &ftmp, 4); '
           f'vm_write32(ctx->gpr[{base}] + {off}, tmp); }}')
    new = (f'{{ float ftmp = mspr_dist_f({kind}, (float)ctx->fpr[{fpr}]); uint32_t tmp; memcpy(&tmp, &ftmp, 4); '
           f'vm_write32(ctx->gpr[{base}] + {off}, tmp); }}   /* {addr}; MSPR_DIST {name} */')
    return old, new


# (file, function, old, new, expected count)
EDITS = [
    ('ppu_recomp_002.cpp', 'func_006000F8',
     'ctx->gpr[3] = (int64_t)(int32_t)((uint32_t)0x4348 << 16);',
     '{ float ftmp = mspr_dist_f(0, 200.0f); uint32_t tmp; memcpy(&tmp, &ftmp, 4); '
     'ctx->gpr[3] = (int64_t)(int32_t)tmp; }   /* 0x006001AC lis r3,0x4348; MSPR_DIST shadow range */', 1),
    ('ppu_recomp_001.cpp', 'func_00360DD4', *st(2, 11, '0x0', 1, '0x0036196C', 'lodBias'), 1),
    ('ppu_recomp_001.cpp', 'func_00360DD4', *st(4, 12, '0xC', 2, '0x003619C8', 'cullThreshold'), 1),
    ('ppu_recomp_001.cpp', 'func_00360DD4', *st(6, 29, '0x10', 3, '0x003619F4', 'shadowCullThreshold'), 1),
    ('ppu_recomp_001.cpp', 'func_00360DD4', *st(10, 28, '0x3C', 4, '0x00361564', 'shadowFadeDistModifier'), 1),
]
# Kk96: the race runs the parser's second lifted entry, func_00360DD8 (the 0x00360DD4 copy never wrote)
EDITS += [('ppu_recomp_009.cpp', 'func_00360DD8') + e[2:] for e in EDITS if e[1] == 'func_00360DD4']

FUNC = re.compile(r'void (func_[0-9A-F]{8})\(ppu_context\* ctx\) \{')


def patch(name, edits):
    path = ST / name
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.dist-tmp')
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
        assert got == e[4], f'{name}: {e[3][-50:]} matched {got}, want {e[4]}'
    if DECL not in '\n'.join(lines[1:4]):
        assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
        eol = '\r' if lines[1].endswith('\r') else ''
        lines.insert(2, DECL + eol)
    path.write_bytes('\n'.join(lines).encode('latin-1'))
    print(f'{name}: {sum(done)} lines patched, {sum(already)} already patched')


for f in sorted({e[0] for e in EDITS}):
    patch(f, [e for e in EDITS if e[0] == f])
