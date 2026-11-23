"""Private (ppucc): VMX lowering prototype.
 (a) the four float helpers call their x86 bodies directly (no g_vmx_fast/cpuid test per op: the
     lifted TU is built with -mssse3 -mfma, so the exe already needs those; both paths give the same
     bits per ppu_vmx.h), always inlined;
 (b) vperm's byte loop becomes two pshufb and a mask select (same bytes: the register image is
     guest byte order, byte i of the image is guest byte i).
"""
import re

BLOCK = r'''
/* ---- ppucc vmxfast prototype ---- */
#define VMXF_AI static inline __attribute__((always_inline, target("ssse3,fma")))
VMXF_AI void vmxf_vaddfp(void* d, const void* a, const void* b, uint32_t s) { vmx_vaddfp_x86(d, a, b, s); }
VMXF_AI void vmxf_vsubfp(void* d, const void* a, const void* b, uint32_t s) { vmx_vsubfp_x86(d, a, b, s); }
VMXF_AI void vmxf_vmaddfp(void* d, const void* a, const void* b, const void* c, uint32_t s) { vmx_vmaddfp_x86(d, a, b, c, s); }
VMXF_AI void vmxf_vnmsubfp(void* d, const void* a, const void* b, const void* c, uint32_t s) { vmx_vnmsubfp_x86(d, a, b, c, s); }
VMXF_AI void vmxf_vperm(void* d, const void* a, const void* b, const void* c) {
    const __m128i A = _mm_loadu_si128((const __m128i*)a), B = _mm_loadu_si128((const __m128i*)b),
                  C = _mm_loadu_si128((const __m128i*)c);
    const __m128i i = _mm_and_si128(C, _mm_set1_epi8(0x0F));
    const __m128i m = _mm_cmpeq_epi8(_mm_and_si128(C, _mm_set1_epi8(0x10)), _mm_set1_epi8(0x10));
    const __m128i r = _mm_or_si128(_mm_andnot_si128(m, _mm_shuffle_epi8(A, i)), _mm_and_si128(m, _mm_shuffle_epi8(B, i)));
    _mm_storeu_si128((__m128i*)d, r); }
#define vmx_vaddfp(d, a, b, s) vmxf_vaddfp((d), (a), (b), (s))
#define vmx_vsubfp(d, a, b, s) vmxf_vsubfp((d), (a), (b), (s))
#define vmx_vmaddfp(d, a, b, c, s) vmxf_vmaddfp((d), (a), (b), (c), (s))
#define vmx_vnmsubfp(d, a, b, c, s) vmxf_vnmsubfp((d), (a), (b), (c), (s))
/* ---- end vmxfast ---- */
'''

VPERM = re.compile(r'\{ uint8_t\* a = \(uint8_t\*\)(&ctx->vr\[\d+\]); uint8_t\* b = \(uint8_t\*\)(&ctx->vr\[\d+\]); '
                   r'uint8_t\* c = \(uint8_t\*\)(&ctx->vr\[\d+\]); uint8_t\* d = \(uint8_t\*\)(&ctx->vr\[\d+\]); '
                   r'uint8_t tmp\[16\]; for \(int i = 0; i < 16; i\+\+\) \{ uint8_t sel = c\[i\] & 0x1F; '
                   r'tmp\[i\] = \(sel < 16\) \? a\[sel\] : b\[sel - 16\]; \} memcpy\(d, tmp, 16\); \}')
INC = '#include "ppu_vmx.h"'


def apply(src):
    i = src.index(INC)
    j = src.index('\n', i) + 1
    src = src[:j] + BLOCK + src[j:]
    return VPERM.sub(lambda m: f'vmxf_vperm({m.group(4)}, {m.group(1)}, {m.group(2)}, {m.group(3)});', src)
