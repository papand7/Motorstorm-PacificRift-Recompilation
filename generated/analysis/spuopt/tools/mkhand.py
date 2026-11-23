"""Insert the hand-written bucket loop into a generated 0x10890 native (gen_native.py output).

  python mkhand.py <in.c> <out.c> [mutate]

The lifted loop at 0x10990/0x10A58 runs i = 1..512 and, per i, stores byte bucket(i) at
LS[base + i + 0x3A4] and the big-endian word i at LS[(base + 4*bucket(i)) & ~3 + 0x360] (base = r17
word 0). The hand-written part does i = 1..511 with plain stores; iteration 512 then runs as
generated, so every register ends as the lifted loop leaves it. Taken only when chaining is open,
interrupts are off and the loop starts as the lifted code always starts it (r11 = 1, r13 = 513);
otherwise the generated loop runs. Steps: two chained edges per skipped iteration.
`mutate` (a gate check only) moves one bucket threshold."""
import sys

src, dst = sys.argv[1], sys.argv[2]
mut = len(sys.argv) > 3
s = open(src).read()
fn0 = s.index('static int nat_00010890(spu_context* ctx) {')
fn1 = s.index('\n}\n', fn0)
body = s[fn0:fn1]
anchor = '    { ctx->pc = 0x10990; if (SPU_CHAIN_OK(ctx)) { ++nst; goto loc_00010990; }'
assert body.count(anchor) == 1, body.count(anchor)
t96 = '97' if mut else '96'
fast = f'''    /* hand-written (mkhand.py): iterations 1..511 of the bucket loop as plain stores */
    if (SPU_CHAIN_OK(ctx) && !ctx->int_enable && R[11]._u32[0] == 1u && R[13]._u32[0] == 513u) {{
        const uint32_t base = R[17]._u32[0];
        for (uint32_t i = 1; i < 512u; i++) {{
            const uint32_t b = i <= 8u ? 1u : i <= 16u ? 2u : i <= 32u ? 3u : i <= 48u ? 4u : i <= 64u ? 5u :
                               i <= {t96}u ? 6u : i <= 128u ? 7u : i <= 160u ? 8u : i <= 192u ? 9u :
                               i <= 256u ? 10u : i <= 320u ? 11u : 12u;
            ls[(base + i + 0x3A4u) & SPU_LS_MASK] = (uint8_t)b;
            const uint32_t be = __builtin_bswap32(i);
            memcpy(&ls[(((base + 4u * b) & ~3u) + 0x360u) & SPU_LS_MASK & ~3u], &be, 4);
        }}
        R[11] = spu_il(512);
        nst += 2u * 511u;
    }}
'''
body = body.replace(anchor, fast + anchor)
s = s[:fn0] + body + s[fn1:]
open(dst, 'w').write('#include <string.h>\n' + s)
print('wrote', dst)
