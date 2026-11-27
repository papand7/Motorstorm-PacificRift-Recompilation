"""Performance page hooks (port-vkgame/main.cpp mspr_vq_f, mspr_vq_b, mspr_gopt; docs/SETTINGS.md, Performance page).
The game's own quality values, read from its own data, each replaced only when its variable is set; unset, every hook
returns what the game read and the game is the original.

1. scripts/viewportquality.xml, GlobalConfig (one entry per viewport count, stride 0x50; parser func_00360DD4 and its
   second lifted entry func_00360DD8, the one the race runs; generated/analysis/lowend_opts/RESULTS.md):
     kind 10  0x003613A0  stfs f4,0x8(r28)    ViewportScaling variableScalingMin (the dynamic resolution floor)
     kind 11  0x0036145C  stfs f12,0x24(r28)  Particles LodScaleMin
     kind 12  0x00361484  stfs f0,0x28(r28)   Particles LodScaleMax
     kind 13  0x003614D4  stfs f4,0x30(r28)   Particles EmissionRateMin
     kind 14  0x003614FC  stfs f6,0x34(r28)   Particles EmissionRateMax
     kind 15  0x003615E0  stfs f0,0x48(r28)   ScreenRush ParticleLimitScalar
     kind 16  0x00361628  stb r21,0x4C(r28)   ScreenRush Rain2Enabled
     kind 17  stb r26,0x4D(r28)               Debris Enabled (the wrecks' loose parts; 0 in the game's 4-viewport entry)
   floats through mspr_vq_f(kind, value), bytes through mspr_vq_b(kind, value).
2. Configs/Includes/ms2_GameOptions.cfg (the boot config's options; each option is read from the loaded document into
   its field by a getter: func_00803E28 float, func_00804350 bool, r6 = the field). After the getter returns, the
   field's address (r6 before the call) goes to mspr_gopt(lr, field), which may write it:
     0x001BD424  ParticleOptions particleEmissionScale (float)
     0x001BF924, 0x001C0564  RenderOptions enableWheelParticles
     0x001BF614, 0x001C0254  RenderOptions enablePostProcessing
     0x001BFA74, 0x001C06B4  RenderOptions enableBoostBlur
   The lifter emits these calls in several fall-through copies (ppu_recomp_000.cpp, 008, 029); every copy is patched,
   the total per call site asserted.

Idempotent; a hard-linked file is copied first, as in the other patch scripts.
usage: python lowend_patch_lifted.py <lifted folder>"""
import os
import pathlib
import re
import shutil
import sys

if len(sys.argv) < 2:
    sys.exit('usage: lowend_patch_lifted.py <lifted folder>')
ST = pathlib.Path(sys.argv[1])
DECL = ('extern "C" float mspr_vq_f(int kind, float v); extern "C" uint32_t mspr_vq_b(int kind, uint32_t v); '
        'extern "C" void mspr_gopt(uint32_t lr, uint32_t field);   /* port main.cpp: Performance page */')

# (kind, fpr, offset)
VQ_F = [(10, 4, '0x8'), (11, 12, '0x24'), (12, 0, '0x28'), (13, 4, '0x30'), (14, 6, '0x34'), (15, 0, '0x48')]
VQ_B = [(16, 21, '0x4C'), (17, 26, '0x4D')]
VQ_FUNCS = {'ppu_recomp_001.cpp': 'func_00360DD4', 'ppu_recomp_009.cpp': 'func_00360DD8'}

# lr: (getter, copies in the tree)
GOPT = {0x001BD424: ('func_00803E28', 1), 0x001BF924: ('func_00804350', 2), 0x001C0564: ('func_00804350', 4),
        0x001BF614: ('func_00804350', 2), 0x001C0254: ('func_00804350', 4),
        0x001BFA74: ('func_00804350', 2), 0x001C06B4: ('func_00804350', 4)}


def vq_old_new_f(kind, fpr, off):
    pat = re.compile(r'^\{ float ftmp = \(float\)ctx->fpr\[%d\]; uint32_t tmp; memcpy\(&tmp, &ftmp, 4\); '
                     r'(vm_write32(?:_ng)?)\(ctx->gpr\[28\] \+ %s, tmp\); \}$' % (fpr, re.escape(off)))
    new = lambda w: (f'{{ float ftmp = mspr_vq_f({kind}, (float)ctx->fpr[{fpr}]); uint32_t tmp; memcpy(&tmp, &ftmp, 4); '
                     f'{w}(ctx->gpr[28] + {off}, tmp); }}   /* MSPR viewportquality kind {kind} */')
    return pat, new


def vq_old_new_b(kind, gpr, off):
    pat = re.compile(r'^(vm_write8(?:_ng)?)\(ctx->gpr\[28\] \+ %s, ctx->gpr\[%d\]\);$' % (re.escape(off), gpr))
    new = lambda w: (f'{w}(ctx->gpr[28] + {off}, mspr_vq_b({kind}, (uint32_t)ctx->gpr[{gpr}]));   '
                     f'/* MSPR viewportquality kind {kind} */')
    return pat, new


def body(lines, fn):
    starts = [i for i, l in enumerate(lines) if l.startswith(f'void {fn}(')]
    assert len(starts) == 1, f'{fn}: {len(starts)} definitions'
    i = starts[0]
    j = i + 1
    while not lines[j].startswith('}'):
        j += 1
    return i, j


def gopt_line(lr, getter):
    return (f'ctx->lr = 0x{lr:08X}; {getter}(ctx); DRAIN_TRAMPOLINE(ctx); '
            f'PPU_TR_RET(ctx, 0x{lr:08X}u, 0x{getter[5:]}u);')


def gopt_new(lr, getter):
    return (f'{{ const uint32_t mspr_gf = (uint32_t)ctx->gpr[6]; {gopt_line(lr, getter)} '
            f'mspr_gopt(0x{lr:08X}u, mspr_gf); }}   /* MSPR game option */')


def load(path):
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.lowend-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
    return path.read_bytes().decode('latin-1').split('\n')


def set_line(lines, i, text):
    eol = '\r' if lines[i].endswith('\r') else ''
    ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    lines[i] = ind + text + eol


def add_decl(lines):
    assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
    if any(l.rstrip('\r') == DECL for l in lines[:12]):
        return 0
    eol = '\r' if lines[1].endswith('\r') else ''
    lines.insert(2, DECL + eol)
    return 1


gopt_total = {lr: 0 for lr in GOPT}
for name in sorted(set(VQ_FUNCS) | {'ppu_recomp_000.cpp', 'ppu_recomp_008.cpp', 'ppu_recomp_029.cpp'}):
    path = ST / name
    if not path.exists():
        continue
    lines = load(path)
    changed = 0
    if name in VQ_FUNCS:
        a, b = body(lines, VQ_FUNCS[name])
        for kind, reg, off in VQ_F + VQ_B:
            pat, new = (vq_old_new_f if kind < 16 else vq_old_new_b)(kind, reg, off)
            hits, done = [], []
            for i in range(a, b):
                s = lines[i].strip()
                m = pat.match(s)
                if m:
                    hits.append((i, m.group(1)))
                elif s.endswith(f'/* MSPR viewportquality kind {kind} */'):
                    done.append(i)
            assert len(hits) + len(done) == 1, f'{name}: kind {kind} found {len(hits)} + patched {len(done)}, want 1'
            for i, w in hits:
                set_line(lines, i, new(w))
                changed += 1
    for lr, (getter, _n) in GOPT.items():
        old, new = gopt_line(lr, getter), gopt_new(lr, getter)
        for i, l in enumerate(lines):
            s = l.strip()
            if s == old:
                set_line(lines, i, new)
                changed += 1
                gopt_total[lr] += 1
            elif s == new:
                gopt_total[lr] += 1
    if changed:
        changed += add_decl(lines)
        path.write_bytes('\n'.join(lines).encode('latin-1'))
    print(f'{name}: {changed} change(s)' if changed else f'{name}: already patched')
for lr, (getter, n) in GOPT.items():
    assert gopt_total[lr] == n, f'call 0x{lr:08X} ({getter}): {gopt_total[lr]} copies, want {n}'
print('lowend hooks: viewportquality 8 fields in 2 parsers, game options %d calls' % sum(gopt_total.values()))
