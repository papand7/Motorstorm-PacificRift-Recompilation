"""Benchmark hooks (the launcher's Benchmark page, MSPR_BENCH=fly|race; port-vkgame/main.cpp, bench_ai.h, bench_run.h).
Unset, every hook returns what the game read and writes nothing: the game is the original.

1. MSPR_BENCH_AI / MSPR_BENCH=race: the reads of a Competitor's controls kind (+0x1930) that pick its active controls
   object go through mspr_bench_ai_ctl(kind, lr, competitor):
     0x00127BC8  lwz r0,0x1930(r3); cmplwi cr7,r0,5; jump table -> &controls   (the getter func_00127BC8)
     0x0012A7D0  lwz r11,0x1930(r3); cmplwi cr1,r11,5; jump table -> controls vfunc +0x20
   The lifter emits the getter body inside every function that falls through into it: ppu_recomp_000.cpp
   func_00127818 (once) and ppu_recomp_008.cpp func_00127A40 .. func_00127BC8 (12 copies); the switch in
   ppu_recomp_000.cpp func_0012A77C and ppu_recomp_008.cpp func_0012A780. All 15 are the same two instructions; each
   is asserted to be followed by its `cmp ... 0x5` within three lines. No write and no other reader is touched.
2. MSPR_BENCH=fly: the end of the disc benchmark's camera path. After the path the benchmark shows static views, each
   labelled with "%s: HotSpot %u" (string 0x00DFFC90, TOC slot r2-0x29BC), formatted in func_00118508 (0x001186E8,
   lifted in ppu_recomp_000.cpp) and its fall-through copy func_00118708 (ppu_recomp_008.cpp). Right after that load the
   hook calls mspr_bench_hotspot() (a note of the time, nothing else). Asserted: once in each of the two functions.

Same lines as generated/analysis/perf60/tools/bench_ai_patch_lifted.py for part 1, so a tree patched by that script is
recognised. Idempotent; a hard-linked file is copied first, as in the other patch scripts.

usage: python bench_patch_lifted.py <lifted folder, e.g. generated/ppu-100>"""
import os
import pathlib
import re
import shutil
import sys

if len(sys.argv) < 2:
    sys.exit('usage: bench_patch_lifted.py <lifted folder>')
ST = pathlib.Path(sys.argv[1])
DECL = 'extern "C" uint32_t mspr_bench_ai_ctl(uint32_t kind, uint32_t lr, uint32_t comp);   /* port main.cpp: MSPR_BENCH_AI */'
DECL2 = 'extern "C" void mspr_bench_hotspot(void);   /* port main.cpp: MSPR_BENCH=fly, the camera path is over */'
AI = {'ppu_recomp_000.cpp': [('ctx->gpr[0] = vm_read32(ctx->gpr[3] + 0x1930);', 1),
                             ('ctx->gpr[11] = vm_read32(ctx->gpr[3] + 0x1930);', 1)],
      'ppu_recomp_008.cpp': [('ctx->gpr[0] = vm_read32(ctx->gpr[3] + 0x1930);', 12),
                             ('ctx->gpr[11] = vm_read32(ctx->gpr[3] + 0x1930);', 1)]}
HOT = {'ppu_recomp_000.cpp': 'func_00118508', 'ppu_recomp_008.cpp': 'func_00118708'}
HOT_LOAD = re.compile(r'^ctx->gpr\[5\] = vm_read32(_ng)?\(ctx->gpr\[2\] \+ -0x29BC\);$')
HOT_CALL = 'mspr_bench_hotspot();   /* MSPR_BENCH=fly */'


def new_of(old):
    lhs, rhs = old.split(' = ', 1)
    return f'{lhs} = mspr_bench_ai_ctl({rhs[:-1]}, (uint32_t)ctx->lr, (uint32_t)ctx->gpr[3]);   /* MSPR_BENCH_AI */'


def body(lines, fn):
    """[first, end) line indexes of fn's definition"""
    starts = [i for i, l in enumerate(lines) if l.startswith(f'void {fn}(')]
    assert len(starts) == 1, f'{fn}: {len(starts)} definitions'
    i = starts[0]
    j = i + 1
    while not lines[j].startswith('}'):
        j += 1
    return i, j


for name in AI:
    path = ST / name
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.bench-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
    lines = path.read_bytes().decode('latin-1').split('\n')
    changed = 0
    for old, n in AI[name]:
        hits = [i for i, l in enumerate(lines) if l.strip() == old]
        done = [i for i, l in enumerate(lines) if l.strip() == new_of(old)]
        assert len(hits) + len(done) == n, f'{name}: {old!r} found {len(hits)} + patched {len(done)}, want {n}'
        for i in hits + done:
            assert 'uint64_t b = (uint64_t)0x5;' in ' '.join(lines[i + 1:i + 4]), f'{name}:{i + 1}: no cmplwi 5 after the read'
        for i in hits:
            eol = '\r' if lines[i].endswith('\r') else ''
            ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
            lines[i] = ind + new_of(old) + eol
            changed += 1
    a, b = body(lines, HOT[name])
    loads = [i for i in range(a, b) if HOT_LOAD.match(lines[i].strip())]
    assert len(loads) == 1, f'{name} {HOT[name]}: {len(loads)} HotSpot format loads, want 1'
    i = loads[0]
    if lines[i + 1].strip() != HOT_CALL:   # after the load: the load's own line is never a branch target's label
        eol = '\r' if lines[i].endswith('\r') else ''
        ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
        lines.insert(i + 1, ind + HOT_CALL + eol)
        changed += 1
    assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
    eol = '\r' if lines[1].endswith('\r') else ''
    for decl in (DECL, DECL2):
        if not any(l.rstrip('\r') == decl for l in lines[:8]):
            lines.insert(2, decl + eol)
            changed += 1
    if changed:
        path.write_bytes('\n'.join(lines).encode('latin-1'))
    print(f'{name}: {changed} change(s)' if changed else f'{name}: already patched')
