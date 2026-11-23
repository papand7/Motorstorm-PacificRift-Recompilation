rep(r"""#include "spu_context.h"
#include <string.h>
#include <math.h>
""", r"""#include "spu_context.h"
#include "spu_hwfloat.h"
#include <string.h>
#include <math.h>
""")
# integer-only fallbacks while the hardware mode is on
rep(r"""static inline uint32_t spu__fa_any(uint32_t x, uint32_t y) { const uint32_t f = spu__fa_fast(x, y); return f ? f : spu__fa_lane(x, y); }
static inline uint32_t spu__fm_any(uint32_t x, uint32_t y) { const uint32_t f = spu__fm_fast(x, y); return f ? f : spu__fm_lane(x, y); }
static inline uint32_t spu__fma_any(uint32_t x, uint32_t y, uint32_t z, uint32_t np, uint32_t nc) {
    const uint32_t f = spu__fma_fast(x, y, z, np, nc); return f ? f : spu__fma_lane(x, y, z, np, nc); }""",
r"""/* While PS3_SPU_HWFLOAT's mode is on (spu_hwfloat.h) the fallbacks take the integer path: the double fast
 * paths are exact under round-toward-zero too, but fma() may be a library routine that assumes the default
 * rounding mode. */
static inline uint32_t spu__fa_any(uint32_t x, uint32_t y) {
    if (SPU_HWF_ON()) return spu__fa_lane(x, y);
    const uint32_t f = spu__fa_fast(x, y); return f ? f : spu__fa_lane(x, y); }
static inline uint32_t spu__fm_any(uint32_t x, uint32_t y) {
    if (SPU_HWF_ON()) return spu__fm_lane(x, y);
    const uint32_t f = spu__fm_fast(x, y); return f ? f : spu__fm_lane(x, y); }
static inline uint32_t spu__fma_any(uint32_t x, uint32_t y, uint32_t z, uint32_t np, uint32_t nc) {
    if (SPU_HWF_ON()) return spu__fma_lane(x, y, z, np, nc);
    const uint32_t f = spu__fma_fast(x, y, z, np, nc); return f ? f : spu__fma_lane(x, y, z, np, nc); }""")
# AVX2 path: hardware mode variants
rep(r"""SPU__X8_INLINE u128 spu_fa(u128 a, u128 b) { return spu__x8_fa(a, b, 0); }
SPU__X8_INLINE u128 spu_fs(u128 a, u128 b) { return spu__x8_fa(a, b, 0x80000000u); }
SPU__X8_INLINE u128 spu_fm(u128 a, u128 b) {
    const __m128i x = spu__x8_ld(a), y = spu__x8_ld(b);""",
r"""#if defined(SPU_HWF_X86)
/* PS3_SPU_HWFLOAT (spu_hwfloat.h): with MXCSR round-toward-zero + DAZ + FTZ, one native vaddps /
 * vsubps / vmulps / vfmadd is the SPU's truncated result for every lane whose result magnitude is
 * below FLT_MAX; an exponent-0 result becomes +0; a lane at or above FLT_MAX (an extended-range
 * operand reads as Inf/NaN, a result >= 2^128 saturates to FLT_MAX) is redone exactly in integers.
 * The instructions are inline asm, not intrinsics: the compiler assumes round-to-nearest when it
 * constant-folds, and must neither fold nor move these out of the mode. FMA3 is required
 * (spu_hwfloat_enabled checks the CPU), so no -mfma build flag is needed. */
SPU__X8_SLOW u128 spu__x8_rz_fix(u128 r, int bad, u128 a, u128 b, u128 c, uint32_t negp, uint32_t negc, int op) {
    for (int i = 0; i < 4; i++) if (bad >> i & 1)
        r._u32[i] = op == 0 ? spu__fa_lane(a._u32[i], b._u32[i] ^ negc)
                  : op == 1 ? spu__fm_lane(a._u32[i], b._u32[i])
                  : spu__fma_lane(a._u32[i], b._u32[i], c._u32[i], negp, negc);
    return r;
}
/* r: the native result. *bad: lanes at or above FLT_MAX in magnitude. Exponent-0 lanes -> +0. */
SPU__X8_INLINE __m128i spu__x8_rz_out(__m128i r, int* bad) {
    const __m128i mag = _mm_and_si128(r, _mm_set1_epi32(0x7FFFFFFF));
    *bad = _mm_movemask_ps(_mm_castsi128_ps(_mm_cmpgt_epi32(mag, _mm_set1_epi32(0x7F7FFFFE))));
    return _mm_andnot_si128(_mm_cmpgt_epi32(_mm_set1_epi32(0x00800000), mag), r);
}
SPU__X8_INLINE u128 spu__x8_fa_rz(u128 a, u128 b, int sub) {
    __m128i x = spu__x8_ld(a);
    const __m128i y = spu__x8_ld(b);
    if (sub) __asm__("vsubps %2, %1, %0" : "=x"(x) : "x"(x), "x"(y));
    else     __asm__("vaddps %2, %1, %0" : "=x"(x) : "x"(x), "x"(y));
    int bad; const u128 r = spu__x8_st(spu__x8_rz_out(x, &bad));
    return __builtin_expect(bad != 0, 0) ? spu__x8_rz_fix(r, bad, a, b, b, 0, sub ? 0x80000000u : 0u, 0) : r;
}
SPU__X8_INLINE u128 spu__x8_fm_rz(u128 a, u128 b) {
    __m128i x = spu__x8_ld(a);
    const __m128i y = spu__x8_ld(b);
    __asm__("vmulps %2, %1, %0" : "=x"(x) : "x"(x), "x"(y));
    int bad; const u128 r = spu__x8_st(spu__x8_rz_out(x, &bad));
    return __builtin_expect(bad != 0, 0) ? spu__x8_rz_fix(r, bad, a, b, b, 0, 0, 1) : r;
}
/* (+-a*b) + (+-c), one truncation: vfmadd213ps x, y, z -> x = y*x + z. */
SPU__X8_INLINE u128 spu__x8_fma_rz(u128 a, u128 b, u128 c, uint32_t negp, uint32_t negc) {
    __m128i x = _mm_xor_si128(spu__x8_ld(a), _mm_set1_epi32((int)negp));
    const __m128i y = spu__x8_ld(b), z = _mm_xor_si128(spu__x8_ld(c), _mm_set1_epi32((int)negc));
    __asm__("vfmadd213ps %2, %1, %0" : "+x"(x) : "x"(y), "x"(z));
    int bad; const u128 r = spu__x8_st(spu__x8_rz_out(x, &bad));
    return __builtin_expect(bad != 0, 0) ? spu__x8_rz_fix(r, bad, a, b, c, negp, negc, 2) : r;
}
SPU__X8_INLINE u128 spu_fa(u128 a, u128 b) { return SPU_HWF_ON() ? spu__x8_fa_rz(a, b, 0) : spu__x8_fa(a, b, 0); }
SPU__X8_INLINE u128 spu_fs(u128 a, u128 b) { return SPU_HWF_ON() ? spu__x8_fa_rz(a, b, 1) : spu__x8_fa(a, b, 0x80000000u); }
#define SPU__X8_FM_RZ(a, b) if (SPU_HWF_ON()) return spu__x8_fm_rz(a, b)
#else
SPU__X8_INLINE u128 spu_fa(u128 a, u128 b) { return spu__x8_fa(a, b, 0); }
SPU__X8_INLINE u128 spu_fs(u128 a, u128 b) { return spu__x8_fa(a, b, 0x80000000u); }
#define SPU__X8_FM_RZ(a, b) (void)0
#endif
SPU__X8_INLINE u128 spu_fm(u128 a, u128 b) {
    SPU__X8_FM_RZ(a, b);
    const __m128i x = spu__x8_ld(a), y = spu__x8_ld(b);""")
rep(r"""SPU__X8_INLINE u128 spu_fma(u128 a, u128 b, u128 c)  { return spu__x8_fma(a, b, c, 0, 0); }            /* a*b + c */
SPU__X8_INLINE u128 spu_fms(u128 a, u128 b, u128 c)  { return spu__x8_fma(a, b, c, 0, 0x80000000u); }  /* a*b - c */
SPU__X8_INLINE u128 spu_fnms(u128 a, u128 b, u128 c) { return spu__x8_fma(a, b, c, 0x80000000u, 0); }  /* c - a*b */""",
r"""#if defined(SPU_HWF_X86)
#define SPU__X8_FMA(a, b, c, np, nc) (SPU_HWF_ON() ? spu__x8_fma_rz(a, b, c, np, nc) : spu__x8_fma(a, b, c, np, nc))
#else
#define SPU__X8_FMA(a, b, c, np, nc) spu__x8_fma(a, b, c, np, nc)
#endif
SPU__X8_INLINE u128 spu_fma(u128 a, u128 b, u128 c)  { return SPU__X8_FMA(a, b, c, 0, 0); }            /* a*b + c */
SPU__X8_INLINE u128 spu_fms(u128 a, u128 b, u128 c)  { return SPU__X8_FMA(a, b, c, 0, 0x80000000u); }  /* a*b - c */
SPU__X8_INLINE u128 spu_fnms(u128 a, u128 b, u128 c) { return SPU__X8_FMA(a, b, c, 0x80000000u, 0); }  /* c - a*b */
#undef SPU__X8_FMA
#undef SPU__X8_FM_RZ""")
# double precision: host rounding around the ops while the mode is on
rep(r"""/* ---- double precision: IEEE, round to nearest (see the header of this section) ---- */""",
r"""/* ---- double precision: IEEE, round to nearest (see the header of this section) ---- */
/* While PS3_SPU_HWFLOAT's mode is on, the double ops run under the host default MXCSR (round to nearest,
 * no FTZ/DAZ). The ldmxcsr asm statements take the operands and the result as memory operands, so every
 * floating-point instruction of the op depends on the first and feeds the second: none can be moved out
 * of the window. */
#if defined(SPU_HWF_X86)
static const unsigned spu__hwf_k_host = SPU_HWF_CSR_HOST, spu__hwf_k_spu = SPU_HWF_CSR;
#define SPU__HWF_D_IN1(a)       const int _hwf = SPU_HWF_ON(); \
    if (_hwf) __asm__ volatile("ldmxcsr %1" : "+m"(a) : "m"(spu__hwf_k_host))
#define SPU__HWF_D_IN2(a, b)    const int _hwf = SPU_HWF_ON(); \
    if (_hwf) __asm__ volatile("ldmxcsr %2" : "+m"(a), "+m"(b) : "m"(spu__hwf_k_host))
#define SPU__HWF_D_IN3(a, b, c) const int _hwf = SPU_HWF_ON(); \
    if (_hwf) __asm__ volatile("ldmxcsr %3" : "+m"(a), "+m"(b), "+m"(c) : "m"(spu__hwf_k_host))
#define SPU__HWF_D_OUT(r)       if (_hwf) __asm__ volatile("ldmxcsr %1" : "+m"(r) : "m"(spu__hwf_k_spu))
#else
#define SPU__HWF_D_IN1(a)       (void)0
#define SPU__HWF_D_IN2(a, b)    (void)0
#define SPU__HWF_D_IN3(a, b, c) (void)0
#define SPU__HWF_D_OUT(r)       (void)0
#endif""")
rep(r"""#define SPU__D_V2(name, op) static inline u128 name(u128 a, u128 b) { u128 r; for (int i = 0; i < 2; i++) { \
    const uint64_t x = spu__dw_get(a, i), y = spu__dw_get(b, i); \
    spu__dw_put(&r, i, (spu__d_isnan(x) || spu__d_isnan(y)) ? 0x7FF8000000000000ull \
                       : spu__d_out(spu__d_in(x) op spu__d_in(y))); } return r; }""",
r"""#define SPU__D_V2(name, op) static inline u128 name(u128 a, u128 b) { u128 r; SPU__HWF_D_IN2(a, b); \
    for (int i = 0; i < 2; i++) { \
    const uint64_t x = spu__dw_get(a, i), y = spu__dw_get(b, i); \
    spu__dw_put(&r, i, (spu__d_isnan(x) || spu__d_isnan(y)) ? 0x7FF8000000000000ull \
                       : spu__d_out(spu__d_in(x) op spu__d_in(y))); } SPU__HWF_D_OUT(r); return r; }""")
rep(r"""static inline u128 spu__dfmx(u128 a, u128 b, u128 c, int negate, int subtract) { u128 r;
    for (int i = 0; i < 2; i++) {""", r"""static inline u128 spu__dfmx(u128 a, u128 b, u128 c, int negate, int subtract) { u128 r;
    SPU__HWF_D_IN3(a, b, c);
    for (int i = 0; i < 2; i++) {""")
rep(r"""        spu__dw_put(&r, i, (negate && !spu__d_isnan(u)) ? u ^ 0x8000000000000000ull : u);
    }
    return r; }""", r"""        spu__dw_put(&r, i, (negate && !spu__d_isnan(u)) ? u ^ 0x8000000000000000ull : u);
    }
    SPU__HWF_D_OUT(r);
    return r; }""")
rep(r"""static inline u128 spu_frds(u128 a) { u128 r;
    for (int i = 0; i < 2; i++) {
        const uint64_t u = spu__dw_get(a, i);
        if (spu__d_isnan(u)) { r._u32[2*i] = 0x7FC00000u; r._u32[2*i+1] = 0; continue; }
        const float f = (float)spu__d_in(u);
        uint32_t w; memcpy(&w, &f, 4);
        r._u32[2*i] = w; r._u32[2*i+1] = 0;
    }
    return r; }""", r"""static inline u128 spu_frds(u128 a) { u128 r;
    SPU__HWF_D_IN1(a);
    for (int i = 0; i < 2; i++) {
        const uint64_t u = spu__dw_get(a, i);
        if (spu__d_isnan(u)) { r._u32[2*i] = 0x7FC00000u; r._u32[2*i+1] = 0; continue; }
        const float f = (float)spu__d_in(u);
        uint32_t w; memcpy(&w, &f, 4);
        r._u32[2*i] = w; r._u32[2*i+1] = 0;
    }
    SPU__HWF_D_OUT(r);
    return r; }""")
rep(r"""static inline u128 spu_dfceq(u128 a, u128 b)  { u128 r; for(int i=0;i<2;i++){ uint64_t m=(spu__dget(a,i)==spu__dget(b,i))?~0ull:0ull; r._u32[i*2]=(uint32_t)(m>>32); r._u32[i*2+1]=(uint32_t)m; } return r; }
static inline u128 spu_dfcmeq(u128 a, u128 b) { u128 r; for(int i=0;i<2;i++){ double x=spu__dget(a,i),y=spu__dget(b,i); if(x<0)x=-x; if(y<0)y=-y; uint64_t m=(x==y)?~0ull:0ull; r._u32[i*2]=(uint32_t)(m>>32); r._u32[i*2+1]=(uint32_t)m; } return r; }""",
r"""static inline u128 spu_dfceq(u128 a, u128 b)  { u128 r; SPU__HWF_D_IN2(a, b); for(int i=0;i<2;i++){ uint64_t m=(spu__dget(a,i)==spu__dget(b,i))?~0ull:0ull; r._u32[i*2]=(uint32_t)(m>>32); r._u32[i*2+1]=(uint32_t)m; } SPU__HWF_D_OUT(r); return r; }
static inline u128 spu_dfcmeq(u128 a, u128 b) { u128 r; SPU__HWF_D_IN2(a, b); for(int i=0;i<2;i++){ double x=spu__dget(a,i),y=spu__dget(b,i); if(x<0)x=-x; if(y<0)y=-y; uint64_t m=(x==y)?~0ull:0ull; r._u32[i*2]=(uint32_t)(m>>32); r._u32[i*2+1]=(uint32_t)m; } SPU__HWF_D_OUT(r); return r; }""")
rep(r"""static inline u128 spu_dfcgt(u128 a, u128 b)  { u128 r; for(int i=0;i<2;i++){ uint64_t m=(spu__dget(a,i)>spu__dget(b,i))?~0ull:0ull; r._u32[i*2]=(uint32_t)(m>>32); r._u32[i*2+1]=(uint32_t)m; } return r; }
static inline u128 spu_dfcmgt(u128 a, u128 b) { u128 r; for(int i=0;i<2;i++){ double x=spu__dget(a,i),y=spu__dget(b,i); if(x<0)x=-x; if(y<0)y=-y; uint64_t m=(x>y)?~0ull:0ull; r._u32[i*2]=(uint32_t)(m>>32); r._u32[i*2+1]=(uint32_t)m; } return r; }""",
r"""static inline u128 spu_dfcgt(u128 a, u128 b)  { u128 r; SPU__HWF_D_IN2(a, b); for(int i=0;i<2;i++){ uint64_t m=(spu__dget(a,i)>spu__dget(b,i))?~0ull:0ull; r._u32[i*2]=(uint32_t)(m>>32); r._u32[i*2+1]=(uint32_t)m; } SPU__HWF_D_OUT(r); return r; }
static inline u128 spu_dfcmgt(u128 a, u128 b) { u128 r; SPU__HWF_D_IN2(a, b); for(int i=0;i<2;i++){ double x=spu__dget(a,i),y=spu__dget(b,i); if(x<0)x=-x; if(y<0)y=-y; uint64_t m=(x>y)?~0ull:0ull; r._u32[i*2]=(uint32_t)(m>>32); r._u32[i*2+1]=(uint32_t)m; } SPU__HWF_D_OUT(r); return r; }""")
