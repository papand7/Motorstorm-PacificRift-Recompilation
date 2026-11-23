"""Add the x86 fast paths for vmaddfp, vnmsubfp, vaddfp and vsubfp to ps3recomp-vkgame's
runtime/ppu/ppu_vmx.h (the per-lane code stays, as the *_lane helpers), the g_vmx_fast switch to
ppu_loader.cpp, and PS3_VMX_FAST to port-vkgame/main.cpp. CRLF files; run once.

usage: py -3 edit_vmx_fast.py"""
import pathlib

R = pathlib.Path(__file__).resolve().parents[4]
VK = R / 'ps3recomp-vkgame'


def edit(path, pairs):
    b = path.read_bytes().decode('utf-8')
    crlf = '\r\n' in b
    s = b.replace('\r\n', '\n')
    for a, n in pairs:
        assert s.count(a) == 1, (path.name, a[:80], s.count(a))
        s = s.replace(a, n)
    if crlf:
        s = s.replace('\n', '\r\n')
    path.write_bytes(s.encode('utf-8'))


FAST = r'''
/* ---- x86 fast paths for the float helpers --------------------------------
 * vmaddfp, vnmsubfp, vaddfp and vsubfp on all four lanes at once: one SSSE3
 * byte swap per operand and, for the fused two, one FMA3 instruction. The bits
 * are the per-lane helpers' (*_lane below): the same IEEE operations with one
 * rounding each (fmaf is the fused multiply-add the FMA instruction is; a
 * subtraction is the addition of the negation), the same NJ flush of inputs
 * and result, and the same NaN rules (a quieted operand A then B, else the
 * default QNaN), so a host NaN's payload never shows. Taken when g_vmx_fast is
 * set (PS3_VMX_FAST=1, or "ab" by the draw engine's [eng-ab] turns; off by
 * default) and the CPU has SSSE3 and FMA3 with AVX state enabled. Tested
 * against the per-lane helpers by runtime/ppu/tests/test_vmx_float_fast.c. */
extern volatile int g_vmx_fast;          /* ppu_loader.cpp */
#ifdef VMX_X86
VMX_INL int vmx_x86_detect(void) {
    unsigned c;
#if defined(_MSC_VER)
    int r[4]; __cpuid(r, 1); c = (unsigned)r[2];
#else
    unsigned a, b, d; if (!__get_cpuid(1, &a, &b, &c, &d)) return 0;
#endif
    const unsigned need = (1u << 9) | (1u << 12) | (1u << 27) | (1u << 28);  /* SSSE3 FMA OSXSAVE AVX */
    if ((c & need) != need) return 0;
    unsigned lo, hi;
    __asm__ volatile("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));
    (void)hi;
    return (lo & 6u) == 6u;                  /* the OS saves XMM and YMM state */
}
VMX_INL int vmx_x86_on(void) {
    static int cpu = -1;
    if (!g_vmx_fast) return 0;
    if (cpu < 0) cpu = vmx_x86_detect();
    return cpu;
}
#define VMX_X86_FN static inline __attribute__((target("ssse3,fma")))
VMX_X86_FN __m128i vmx_x86_swap(__m128i v) {
    return _mm_shuffle_epi8(v, _mm_setr_epi8(3, 2, 1, 0, 7, 6, 5, 4, 11, 10, 9, 8, 15, 14, 13, 12));
}
VMX_X86_FN __m128i vmx_x86_ld(const void* p) { return vmx_x86_swap(_mm_loadu_si128((const __m128i*)p)); }
VMX_X86_FN void vmx_x86_st(void* p, __m128i v) { _mm_storeu_si128((__m128i*)p, vmx_x86_swap(v)); }
/* vmx_flush on each lane: an exponent of 0 keeps only the sign. */
VMX_X86_FN __m128i vmx_x86_flush(__m128i x, uint32_t vscr) {
    if (!(vscr & VMX_NJ)) return x;
    const __m128i z = _mm_cmpeq_epi32(_mm_and_si128(x, _mm_set1_epi32(0x7F800000)), _mm_setzero_si128());
    return _mm_andnot_si128(_mm_and_si128(z, _mm_set1_epi32(0x7FFFFFFF)), x);
}
/* vmx_isnan on each lane: all ones where the lane is a NaN. */
VMX_X86_FN __m128i vmx_x86_isnan(__m128i x) {
    return _mm_cmpgt_epi32(_mm_and_si128(x, _mm_set1_epi32(0x7FFFFFFF)), _mm_set1_epi32(0x7F800000));
}
VMX_X86_FN __m128i vmx_x86_sel(__m128i m, __m128i a, __m128i b) {
    return _mm_or_si128(_mm_and_si128(m, a), _mm_andnot_si128(m, b));
}
VMX_X86_FN __m128i vmx_x86_fix(__m128i r) { return vmx_x86_sel(vmx_x86_isnan(r), _mm_set1_epi32(0x7FC00000), r); }
VMX_X86_FN __m128i vmx_x86_vnan2(__m128i r, __m128i x, __m128i y) {
    const __m128i q = _mm_set1_epi32(0x7FC00000);
    r = vmx_x86_sel(vmx_x86_isnan(y), _mm_or_si128(y, q), vmx_x86_fix(r));
    return vmx_x86_sel(vmx_x86_isnan(x), _mm_or_si128(x, q), r);
}
VMX_X86_FN void vmx_vaddfp_x86(void* d, const void* a, const void* b, uint32_t vscr) {
    const __m128i x = vmx_x86_flush(vmx_x86_ld(a), vscr), y = vmx_x86_flush(vmx_x86_ld(b), vscr);
    const __m128i r = _mm_castps_si128(_mm_add_ps(_mm_castsi128_ps(x), _mm_castsi128_ps(y)));
    vmx_x86_st(d, vmx_x86_flush(vmx_x86_vnan2(r, x, y), vscr));
}
VMX_X86_FN void vmx_vsubfp_x86(void* d, const void* a, const void* b, uint32_t vscr) {
    const __m128i x = vmx_x86_flush(vmx_x86_ld(a), vscr), y = vmx_x86_flush(vmx_x86_ld(b), vscr);
    const __m128i r = _mm_castps_si128(_mm_sub_ps(_mm_castsi128_ps(x), _mm_castsi128_ps(y)));
    vmx_x86_st(d, vmx_x86_flush(vmx_x86_vnan2(r, x, y), vscr));
}
/* fmaf(x, z, y) */
VMX_X86_FN void vmx_vmaddfp_x86(void* d, const void* a, const void* b, const void* c, uint32_t vscr) {
    const __m128 x = _mm_castsi128_ps(vmx_x86_flush(vmx_x86_ld(a), vscr));
    const __m128 y = _mm_castsi128_ps(vmx_x86_flush(vmx_x86_ld(b), vscr));
    const __m128 z = _mm_castsi128_ps(vmx_x86_flush(vmx_x86_ld(c), vscr));
    vmx_x86_st(d, vmx_x86_flush(vmx_x86_fix(_mm_castps_si128(_mm_fmadd_ps(x, z, y))), vscr));
}
/* -fmaf(x, z, -y): x * z - y, rounded once, then the sign flipped. (Not
 * -(x * z) + y, which is +0 where this is -0.) */
VMX_X86_FN void vmx_vnmsubfp_x86(void* d, const void* a, const void* b, const void* c, uint32_t vscr) {
    const __m128 x = _mm_castsi128_ps(vmx_x86_flush(vmx_x86_ld(a), vscr));
    const __m128 y = _mm_castsi128_ps(vmx_x86_flush(vmx_x86_ld(b), vscr));
    const __m128 z = _mm_castsi128_ps(vmx_x86_flush(vmx_x86_ld(c), vscr));
    const __m128i r = _mm_xor_si128(_mm_castps_si128(_mm_fmsub_ps(x, z, y)), _mm_set1_epi32((int)0x80000000u));
    vmx_x86_st(d, vmx_x86_flush(vmx_x86_fix(r), vscr));
}
#endif
'''

edit(VK / 'runtime/ppu/ppu_vmx.h', [
    ('''#include <stdint.h>
#include <string.h>
#include <math.h>
''', '''#include <stdint.h>
#include <string.h>
#include <math.h>
#if (defined(__x86_64__) || defined(_M_X64)) && (defined(__clang__) || defined(__GNUC__))
#define VMX_X86 1                            /* the float fast paths below */
#include <immintrin.h>
#if defined(_MSC_VER)
#include <intrin.h>
#else
#include <cpuid.h>
#endif
#endif
'''),
    ('''VMX_FBIN(vmx_vaddfp, vmx_f(x) + vmx_f(y), 1)
VMX_FBIN(vmx_vsubfp, vmx_f(x) - vmx_f(y), 1)
VMX_FBIN(vmx_vmaxfp, vmx_maxf(vmx_f(x), vmx_f(y)), 0)
VMX_FBIN(vmx_vminfp, vmx_minf(vmx_f(x), vmx_f(y)), 0)

VMX_INL void vmx_vmaddfp(VMX_D, VMX_A, VMX_B, VMX_C, uint32_t vscr) { VMX_ARGS_PREP; const uint8_t* c = (const uint8_t*)c_;
    for (int i = 0; i < 4; i++) {
        float x = vmx_f(vmx_flush(vmx_w(a, i), vscr)), y = vmx_f(vmx_flush(vmx_w(b, i), vscr)),
              z = vmx_f(vmx_flush(vmx_w(c, i), vscr));
        vmx_sw(r, i, vmx_flush(vmx_fix(vmx_u(fmaf(x, z, y))), vscr)); } VMX_OUT; }
VMX_INL void vmx_vnmsubfp(VMX_D, VMX_A, VMX_B, VMX_C, uint32_t vscr) { VMX_ARGS_PREP; const uint8_t* c = (const uint8_t*)c_;
    for (int i = 0; i < 4; i++) {
        float x = vmx_f(vmx_flush(vmx_w(a, i), vscr)), y = vmx_f(vmx_flush(vmx_w(b, i), vscr)),
              z = vmx_f(vmx_flush(vmx_w(c, i), vscr));
        vmx_sw(r, i, vmx_flush(vmx_fix(vmx_u(-fmaf(x, z, -y))), vscr)); } VMX_OUT; }
''', '''VMX_FBIN(vmx_vaddfp_lane, vmx_f(x) + vmx_f(y), 1)
VMX_FBIN(vmx_vsubfp_lane, vmx_f(x) - vmx_f(y), 1)
VMX_FBIN(vmx_vmaxfp, vmx_maxf(vmx_f(x), vmx_f(y)), 0)
VMX_FBIN(vmx_vminfp, vmx_minf(vmx_f(x), vmx_f(y)), 0)

VMX_INL void vmx_vmaddfp_lane(VMX_D, VMX_A, VMX_B, VMX_C, uint32_t vscr) { VMX_ARGS_PREP; const uint8_t* c = (const uint8_t*)c_;
    for (int i = 0; i < 4; i++) {
        float x = vmx_f(vmx_flush(vmx_w(a, i), vscr)), y = vmx_f(vmx_flush(vmx_w(b, i), vscr)),
              z = vmx_f(vmx_flush(vmx_w(c, i), vscr));
        vmx_sw(r, i, vmx_flush(vmx_fix(vmx_u(fmaf(x, z, y))), vscr)); } VMX_OUT; }
VMX_INL void vmx_vnmsubfp_lane(VMX_D, VMX_A, VMX_B, VMX_C, uint32_t vscr) { VMX_ARGS_PREP; const uint8_t* c = (const uint8_t*)c_;
    for (int i = 0; i < 4; i++) {
        float x = vmx_f(vmx_flush(vmx_w(a, i), vscr)), y = vmx_f(vmx_flush(vmx_w(b, i), vscr)),
              z = vmx_f(vmx_flush(vmx_w(c, i), vscr));
        vmx_sw(r, i, vmx_flush(vmx_fix(vmx_u(-fmaf(x, z, -y))), vscr)); } VMX_OUT; }
''' + FAST + '''
#ifdef VMX_X86
#define VMX_FAST2(name) \\
VMX_INL void name(VMX_D, VMX_A, VMX_B, uint32_t vscr) { \\
    if (vmx_x86_on()) name##_x86(d_, a_, b_, vscr); else name##_lane(d_, a_, b_, vscr); }
#define VMX_FAST3(name) \\
VMX_INL void name(VMX_D, VMX_A, VMX_B, VMX_C, uint32_t vscr) { \\
    if (vmx_x86_on()) name##_x86(d_, a_, b_, c_, vscr); else name##_lane(d_, a_, b_, c_, vscr); }
#else
#define VMX_FAST2(name) \\
VMX_INL void name(VMX_D, VMX_A, VMX_B, uint32_t vscr) { name##_lane(d_, a_, b_, vscr); }
#define VMX_FAST3(name) \\
VMX_INL void name(VMX_D, VMX_A, VMX_B, VMX_C, uint32_t vscr) { name##_lane(d_, a_, b_, c_, vscr); }
#endif
VMX_FAST2(vmx_vaddfp)
VMX_FAST2(vmx_vsubfp)
VMX_FAST3(vmx_vmaddfp)
VMX_FAST3(vmx_vnmsubfp)
'''),
])

edit(VK / 'runtime/ppu/ppu_loader.cpp', [
    ('''extern "C" int g_resv_store_active = -1;   /* -1 uninit, 0 off, 1 on */
''', '''extern "C" int g_resv_store_active = -1;   /* -1 uninit, 0 off, 1 on */

/* ppu_vmx.h: the x86 fast paths of the float VMX helpers. Off by default; the
 * host sets it from PS3_VMX_FAST (port-vkgame/main.cpp). */
extern "C" volatile int g_vmx_fast = 0;
'''),
])

edit(R / 'port-vkgame/main.cpp', [
    ('''int      rsx_draw_engine_ab_phase(void);      /* the engine's in-run A/B side */
''', '''int      rsx_draw_engine_ab_phase(void);      /* the engine's in-run A/B side */
extern volatile int g_vmx_fast;               /* PS3_VMX_FAST: ppu_vmx.h's x86 fast paths */
'''),
    ('''    const char* sab_env = getenv("MSPR_STORE_INLINE_AB");
    int store_ab = sab_env && !strcmp(sab_env, "1");
''', '''    const char* sab_env = getenv("MSPR_STORE_INLINE_AB");
    int store_ab = sab_env && !strcmp(sab_env, "1");
    /* PS3_VMX_FAST=1 (off by default): the float VMX helpers' x86 fast paths
     * (ppu_vmx.h), the same bits as the per-lane code; "ab": on and off by
     * the same turns. */
    const char* vmx_env = getenv("PS3_VMX_FAST");
    const int vmx_ab = vmx_env && !strcmp(vmx_env, "ab");
    if (vmx_env && !strcmp(vmx_env, "1")) g_vmx_fast = 1;
    if (vmx_env) fprintf(stderr, "[vmx-fast] PS3_VMX_FAST=%s: float VMX helpers on x86 fast paths%s\\n",
                         vmx_env, vmx_ab ? " by turns" : "");
'''),
    ('''        if (store_ab == 2) __atomic_store_n(&vm_st_inline, rsx_draw_engine_ab_phase(), __ATOMIC_RELEASE);
''', '''        if (store_ab == 2) __atomic_store_n(&vm_st_inline, rsx_draw_engine_ab_phase(), __ATOMIC_RELEASE);
        if (vmx_ab) g_vmx_fast = rsx_draw_engine_ab_phase();
'''),
])
print('ok')
