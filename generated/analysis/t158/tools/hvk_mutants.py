"""T158: mutants of the C1 (--chain-chunks) solver lift, to show the function-level harness detects
chaining errors. Each mutant is one edit in the hot group c1_solver_spu_grp_00007C48:
  m1  a backward chained jump to the wrong label (same pc stored, wrong code continues)
  m2  a chained conditional with its condition inverted
  m3  one arithmetic op replaced (the group's first a -> sf)
  m4  SPU_CHAIN without the step count (a chained hop that is not counted)
Writes <out>/<m>/solver/{c0,c1,table.c}; build each with hvk_build.py and run `diff`.
  py -3 hvk_mutants.py <hvk lift dir> <out dir>"""
import shutil
import sys
from pathlib import Path

LIFT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
src = (LIFT / 'solver' / 'c1' / 'spu_recomp.c').read_text(encoding='utf-8')
g0 = src.index('static void c1_solver_spu_grp_00007C48(spu_context* ctx, uint32_t entry, uint8_t* SPU_LS_RESTRICT ls) {')
g1 = src.index('\n}\n', g0)
grp = src[g0:g1]


def once(text, old, new):
    assert text.count(old) >= 1, old
    return text.replace(old, new, 1)


M = {
    'm1': lambda g: once(g, 'SPU_CHAIN_BACK(ctx, 0x7CB0u, loc_00007CB0,', 'SPU_CHAIN_BACK(ctx, 0x7CB0u, loc_00007CE8,'),
    'm2': lambda g: once(g, 'if (ctx->gpr[25]._u32[0] != 0) SPU_CHAIN(ctx, 0x7D94u,', 'if (ctx->gpr[25]._u32[0] == 0) SPU_CHAIN(ctx, 0x7D94u,'),
    'm3': lambda g: once(g, '= spu_a(', '= spu_sf('),
    'm4': lambda g: g,
}
for name, f in M.items():
    d = OUT / name / 'solver'
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(LIFT / 'solver' / 'c0', d / 'c0')
    (d / 'c1').mkdir(parents=True)
    shutil.copy2(LIFT / 'solver' / 'c1' / 'spu_recomp.h', d / 'c1' / 'spu_recomp.h')
    shutil.copy2(LIFT / 'solver' / 'table.c', d / 'table.c')
    s = src[:g0] + f(grp) + src[g1:]
    if name == 'm4':
        s = s.replace('#include "spu_helpers.h"\n', '#include "spu_helpers.h"\n#undef SPU_CHAIN\n'
                      '#define SPU_CHAIN(ctx, tgt, label, fn) do { (ctx)->pc = (tgt); if (SPU_CHAIN_OK(ctx)) goto label; '
                      'g_spu_trampoline_fn = (fn); return; } while (0)\n', 1)
    assert s != src
    (d / 'c1' / 'spu_recomp.c').write_text(s, encoding='utf-8')
    print('wrote', d)
