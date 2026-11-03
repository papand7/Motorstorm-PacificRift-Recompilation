"""T82: apply the spu_aot_prof hooks to runtime/spu/spu_drain.c byte-exactly (the file mixes LF and CRLF
lines; only inserted lines are added, every existing byte is kept). Usage: py -3 -I patch_drain.py <file>"""
import sys

p = sys.argv[1]
b = open(p, 'rb').read()


def ins_after(b, anchor, add):
    i = b.find(anchor)
    assert i >= 0 and b.find(anchor, i + 1) < 0, anchor
    j = i + len(anchor)
    return b[:j] + add + b[j:]


def ins_before(b, anchor, add):
    i = b.find(anchor)
    assert i >= 0 and b.find(anchor, i + 1) < 0, anchor
    return b[:i] + add + b[i:]


b = ins_after(b, b'#include "spu_context.h"\n', b'#include "spu_reloc.h"   /* spu_aot_prof_* */\n')
# drain-resume success (before the trampoline is set) and restart (before the fallthrough to the unwind)
a1 = b'(int)ctx->resident_ovl); }'
i = b.find(a1); assert i >= 0 and b.find(a1, i + 1) < 0
eol = b'\r\n' if b[i + len(a1):i + len(a1) + 2] == b'\r\n' else b'\n'
b = ins_after(b, a1 + eol, b'                if (__builtin_expect(spu_aot_prof_on() != 0, 0))' + eol +
              b'                    spu_aot_prof_note(SPU_AOT_PROF_RESUME, spu_aot_prof_owner(ctx, pc), pc, 0, 0);' + eol)
a2 = b'                g_spu_trampoline_fn = spu_indirect_branch;' + eol + b'                continue;' + eol + b'            }' + eol
b = ins_after(b, a2, b'            if (__builtin_expect(spu_aot_prof_on() != 0, 0))' + eol +
              b'                spu_aot_prof_note(SPU_AOT_PROF_RESTART, spu_aot_prof_owner(ctx, pc), pc, 0, 0);' + eol)
# iret below the top-level driver
a3 = b'                    spu_restart_dispatch(ctx);'
i = b.find(a3); assert i >= 0
k = b.rfind(b'\n', 0, i) + 1
eol3 = b'\r\n' if b[i + len(a3):i + len(a3) + 2] == b'\r\n' else b'\n'
b = b[:k] + (b'                    if (__builtin_expect(spu_aot_prof_on() != 0, 0))' + eol3 +
             b'                        spu_aot_prof_note(SPU_AOT_PROF_IRQ_RESTART, spu_aot_prof_owner(ctx, ctx->pc), ctx->pc, 0, 0);' + eol3) + b[k:]
assert b.count(a3) == 1
open(p, 'wb').write(b)
print('patched', p)
