"""T175: vfp_vertex_direct builds each slot in registers and stores it once. usage: py -3 patch_lane_t175.py <tree>"""
import sys
F = sys.argv[1] + '/include/ps3emu/vp_fetch_plan.h'
s = open(F, encoding='utf-8', errors='surrogateescape', newline='').read()
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')
a = s[s.index('/* vpx_vertex_direct through the plan;'):s.index('#ifdef __cplusplus\n}\n#endif\n#endif')]
b = '''/* vpx_vertex_direct through the plan; the plan keeps vpx's slot order. On x86-64 the planned kinds build their
 * 16 bytes in registers and store them once, in slot order: no 16-byte read of 4-byte stores (a failed store
 * forward), and no out-of-order small stores into write-combined memory. The same bits as vfp_fetch. */
#if defined(__x86_64__) || defined(_M_X64)
static inline uint32_t vfp_bits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }
static inline uint32_t vfp_comp(const vfp_tables* t, uint8_t kind, const uint8_t* q, uint32_t k)
{
    if (kind == VFP_SF) {
        const uint32_t h = ((uint32_t)q[k * 2] << 8) | q[k * 2 + 1];
        return t->sf_base[h >> 10] | ((h & 0x3FFu) << 13 & t->sf_man[h >> 10]);
    }
    if (kind == VFP_F32) { uint32_t w; memcpy(&w, q + k * 4, 4); return vfp_bswap32(w); }
    return vfp_bits(t->ub[q[k]]);
}
static inline __m128i vfp_lane(vfp_plan* p, vfp_attr* a, const vfp_tables* t, uint32_t vi, const float dflt[4])
{
    const uint32_t off = a->base + vi * a->stride;
    if ((off >> 20) != a->page) {
        a->page = off >> 20;
        a->page_ea = p->resolve(a->local, off) - (off & 0xFFFFFu);
        p->page_misses++;
    }
    const uint8_t* q = p->vm + (uint32_t)(a->page_ea + (off & 0xFFFFFu));
    if (a->kind == VFP_CMP) {
        const uint32_t w = ((uint32_t)q[0] << 24) | ((uint32_t)q[1] << 16) | ((uint32_t)q[2] << 8) | q[3];
        return _mm_set_epi32(0x3F800000, (int)vfp_bits(t->cmp10[(w >> 22) & 0x3FFu]), (int)vfp_bits(t->cmp11[(w >> 11) & 0x7FFu]), (int)vfp_bits(t->cmp11[w & 0x7FFu]));
    }
    const uint32_t n = a->n;
    const uint32_t x0 = vfp_comp(t, a->kind, q, 0);   /* n is 1 to 4 */
    const uint32_t x1 = n > 1 ? vfp_comp(t, a->kind, q, 1) : vfp_bits(dflt[1]);
    const uint32_t x2 = n > 2 ? vfp_comp(t, a->kind, q, 2) : vfp_bits(dflt[2]);
    const uint32_t x3 = n > 3 ? vfp_comp(t, a->kind, q, 3) : vfp_bits(dflt[3]);
    return _mm_set_epi32((int)x3, (int)x2, (int)x1, (int)x0);
}
#endif
static inline void vfp_vertex_direct(const vpx_cache* c, vfp_plan* p, uint32_t vi, uint8_t* d)
{
#if defined(__x86_64__) || defined(_M_X64)
    const vfp_tables* t = vfp_tables_get();
#endif
    for (int k = 0; k < p->nact; k++) {
        vfp_attr* a = &p->a[k];
        uint8_t* s = d + (size_t)k * 16u;
#if defined(__x86_64__) || defined(_M_X64)
        if (a->kind != VFP_GENERIC) { _mm_storeu_si128((__m128i*)(void*)s, vfp_lane(p, a, t, vi, c->tmpl[a->slot])); continue; }
#endif
        vfp_fetch(p, a, vi, c->tmpl[a->slot], (float*)(void*)s);
    }
}

'''
s = s.replace(a, b)
x = '#include "ps3emu/vp_expand.h"\n'
assert s.count(x) == 1
s = s.replace(x, x + '#if defined(__x86_64__) || defined(_M_X64)\n#include <emmintrin.h>\n#endif\n')
if crlf:
    s = s.replace('\n', '\r\n')
open(F, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(s)
