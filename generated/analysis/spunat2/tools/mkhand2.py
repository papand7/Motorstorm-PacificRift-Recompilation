"""Insert the range-filled bucket loop into a generated 0x10890 native (gen_native.py output, R_n names).

  python mkhand2.py <in.c> <out.c> [mutate]

The bucket(i) of the lifted loop is constant over twelve ranges of i = 1..511, and the word stored
for bucket b at LS[((base + 4*b) & ~3) + 0x360] is the last i of its range (later iterations overwrite
it with the same slot). So each range is filled with its byte value in a plain loop and its word is
stored once, with the range end. The byte slots (base + i + 0x3A4) and the word slots (0x364..0x390)
do not overlap, so the order of the two kinds of store does not change the result.
Iteration 512 runs as generated; the taken condition is the same as mkhand.py's.
`mutate` (a gate check only) moves the bucket 6 threshold 96 -> 97."""
import sys

src, dst = sys.argv[1], sys.argv[2]
mut = len(sys.argv) > 3
s = open(src, encoding='utf-8').read()
fn0 = s.index('static int nat_00010890(spu_context* ctx) {')
fn1 = s.index('\n}\n', fn0)
body = s[fn0:fn1]
anchor = '    { ctx->pc = 0x10990; if (_ck || (SPU_CHAIN_OK(ctx))) { ++nst; goto loc_00010990_fast2; }'
assert body.count(anchor) == 1, body.count(anchor)
hi = [8, 16, 32, 48, 64, 96, 128, 160, 192, 256, 320, 511]
if mut:
    hi[5] = 97
fast = f'''    /* hand-written (mkhand2.py): buckets of i = 1..511 as range fills, one word store per bucket */
    if (SPU_CHAIN_OK(ctx) && !ctx->int_enable && R_11._u32[0] == 1u && R_13._u32[0] == 513u) {{
        const uint32_t base = R_17._u32[0];
        static const uint32_t hi[12] = {{{', '.join(str(h) + 'u' for h in hi)}}};
        uint32_t lo = 1u;
        for (uint32_t b = 1u; b <= 12u; b++) {{
            const uint32_t end = hi[b - 1u];
            for (uint32_t i = lo; i <= end; i++) ls[(base + i + 0x3A4u) & SPU_LS_MASK] = (uint8_t)b;
            const uint32_t be = __builtin_bswap32(end);
            memcpy(&ls[(((base + 4u * b) & ~3u) + 0x360u) & SPU_LS_MASK & ~3u], &be, 4);
            lo = end + 1u;
        }}
        R_11 = spu_il(512);
        nst += 2u * 511u;
    }}
'''
body = body.replace(anchor, fast + anchor)
s = s[:fn0] + body + s[fn1:]
if '#include <string.h>' not in s:
    s = '#include <string.h>\n' + s
open(dst, 'w', encoding='utf-8').write(s)
print('wrote', dst)
