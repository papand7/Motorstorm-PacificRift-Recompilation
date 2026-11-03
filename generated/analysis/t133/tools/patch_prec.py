"""T133: RSX_FP_PRECISION=1: clamp each FP result to its OPDEST precision range (one-shot)."""
import sys
root = sys.argv[1]


def patch(path, pairs):
    s = open(path, newline='', encoding='utf-8').read().replace('\r\n', '\n')
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:80], s.count(a))
        s = s.replace(a, b)
    open(path, 'w', newline='', encoding='utf-8').write(s.replace('\n', '\r\n'))


V = root + '/libs/video/'
patch(V + 'rsx_fp_decompiler.h', [
    ('''/* Kept from this tree (see the .c) -- used by rsx_d3d12_backend.c. */
''', '''/* OPDEST [23:22] precision: 0 FP32, 1 FP16, 2 FX12, 3 FX9. With the clamp
 * on, each written result is clamped to its precision's range before the
 * saturate modifier: FP16 +-65504, FX12 [-2, 2], FX9 [-1, 1] (the ranges
 * RPCS3's ClampValue uses). Off (the default): results keep FP32 range.
 * The initial mode is RSX_FP_PRECISION ("1" = on), read once. */
void rsx_fp_set_precision_clamp(int on);
int  rsx_fp_precision_clamp_on(void);
/* Instructions of the program per precision (counts[0..3]); branches and
 * instructions with neither a destination nor a condition write are skipped. */
void rsx_fp_precision_counts(const u8* ucode, u32 max_bytes, u32 counts[4]);

/* Kept from this tree (see the .c) -- used by rsx_d3d12_backend.c. */
'''),
])
patch(V + 'rsx_fp_decompiler.c', [
    ('''static void fp_shadow_helper(Out* p, u32 unit, u32 cube_mask,
''', '''#define FP_PREC_SHIFT 22   /* OPDEST [23:22]: 0 FP32, 1 FP16, 2 FX12, 3 FX9 */
static int s_fp_prec_clamp = -1;
void rsx_fp_set_precision_clamp(int on) { s_fp_prec_clamp = on ? 1 : 0; }
int rsx_fp_precision_clamp_on(void)
{
    if (s_fp_prec_clamp < 0) {
        const char* e = getenv("RSX_FP_PRECISION");
        s_fp_prec_clamp = (e && e[0] == '1' && !e[1]) ? 1 : 0;
    }
    return s_fp_prec_clamp;
}

void rsx_fp_precision_counts(const u8* ucode, u32 max_bytes, u32 counts[4])
{
    counts[0] = counts[1] = counts[2] = counts[3] = 0;
    if (!ucode) return;
    for (u32 off = 0; off + 16 <= max_bytes;) {
        const u32 w0 = rsx_fp_read_word(ucode + off);
        const u32 w1 = rsx_fp_read_word(ucode + off + 4);
        const u32 w2 = rsx_fp_read_word(ucode + off + 8);
        const u32 w3 = rsx_fp_read_word(ucode + off + 12);
        if (!(w2 & FP_BRANCH) && (!(w0 & FP_OUT_NONE) || (w0 & FP_COND_WRITE)))
            counts[(w0 >> FP_PREC_SHIFT) & 3u]++;
        off += 16;
        if (!(w2 & FP_BRANCH) && ((w1 & 3u) == 2 || (w2 & 3u) == 2 || (w3 & 3u) == 2)) off += 16;
        if (w0 & FP_END) break;
    }
}

static void fp_shadow_helper(Out* p, u32 unit, u32 cube_mask,
'''),
    ('''            const char* sat = (w0 & FP_OUT_SAT) ? " _v = saturate(_v);" : "";
''', '''            /* RSX_FP_PRECISION: the precision clamp comes after the result
             * scale and before saturate (rsx_fp_set_precision_clamp). */
            static const char* prec_txt[4] = { "", " _v = clamp(_v, -65504.0, 65504.0);",
                                               " _v = clamp(_v, -2.0, 2.0);", " _v = clamp(_v, -1.0, 1.0);" };
            char sat[96];
            snprintf(sat, sizeof sat, "%s%s",
                     rsx_fp_precision_clamp_on() ? prec_txt[(w0 >> FP_PREC_SHIFT) & 3u] : "",
                     (w0 & FP_OUT_SAT) ? " _v = saturate(_v);" : "");
'''),
])
print('ok')
