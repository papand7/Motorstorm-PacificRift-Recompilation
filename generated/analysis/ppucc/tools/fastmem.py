"""Private (ppucc): guest-memory fast-path prototype (candidate 3) as a block injected after
#include "ppu_recomp.h" in a lifted TU, plus the per-function base local.
  ldg: 1 = load page-gate table (one byte), 2 = exact range gate on hoisted runtime limits
       (vm_ld_lim / vm_ld_refp, no memory read per access), 0 = no gate (needs a fault-backed runtime)
  stg: 1 = store page gate (vm_st_page only), 0 = none
"""
import re


def block(ldg=1, stg=1):
    return r'''
/* ---- ppucc fastmem prototype ---- */
static inline uint8_t* fm_base_get(void) { return vm_base; }
typedef uint16_t __attribute__((aligned(1))) fm_u16; typedef uint32_t __attribute__((aligned(1))) fm_u32;
typedef uint64_t __attribute__((aligned(1))) fm_u64;
#define FM_LDG %d
#define FM_STG %d
extern "C" uint32_t vm_ld_lim, vm_ld_refp;
static inline __attribute__((always_inline)) int fm_ld_ok(uint32_t ea, uint32_t n, uint32_t lim, uint32_t ref) {
#if FM_LDG == 2
    return (uint32_t)(ea - 0x10000u) <= lim - n && (ea >> 16) != ref;
#elif FM_LDG == 1
    (void)lim; (void)ref; return vm_ld_page[ea >> 16] && (ea & 0xFFFFu) <= 0x10000u - n;
#else
    (void)ea; (void)n; (void)lim; (void)ref; return 1;
#endif
}
static inline __attribute__((always_inline)) int fm_st_ok(uint32_t ea, uint32_t n) { return !FM_STG || (vm_st_page[ea >> 16] && (ea & 0xFFFFu) <= 0x10000u - n); }
#define FM_A uint8_t* b, uint32_t lim, uint32_t ref, uint64_t a
static inline uint8_t  fm_rd8 (FM_A) { uint32_t e = (uint32_t)a; if (__builtin_expect(fm_ld_ok(e, 1, lim, ref), 1)) return *(volatile const uint8_t*)(b + e); return vm_read8_cold(a); }
static inline uint16_t fm_rd16(FM_A) { uint32_t e = (uint32_t)a; if (__builtin_expect(fm_ld_ok(e, 2, lim, ref), 1)) return __builtin_bswap16(*(volatile const fm_u16*)(b + e)); return vm_read16_cold(a); }
static inline uint32_t fm_rd32(FM_A) { uint32_t e = (uint32_t)a; if (__builtin_expect(fm_ld_ok(e, 4, lim, ref), 1)) return __builtin_bswap32(*(volatile const fm_u32*)(b + e)); return vm_read32_cold(a); }
static inline uint64_t fm_rd64(FM_A) { uint32_t e = (uint32_t)a; if (__builtin_expect(fm_ld_ok(e, 8, lim, ref), 1)) return __builtin_bswap64(*(volatile const fm_u64*)(b + e)); return vm_read64_cold(a); }
static inline void fm_wr8 (uint8_t* b, uint64_t a, uint8_t v)  { uint32_t e = (uint32_t)a; if (__builtin_expect(fm_st_ok(e, 1), 1)) { *(volatile uint8_t*)(b + e) = v; return; } vm_write8_cold(a, v); }
static inline void fm_wr16(uint8_t* b, uint64_t a, uint16_t v) { uint32_t e = (uint32_t)a; if (__builtin_expect(fm_st_ok(e, 2), 1)) { *(volatile fm_u16*)(b + e) = __builtin_bswap16(v); return; } vm_write16_cold(a, v); }
static inline void fm_wr32(uint8_t* b, uint64_t a, uint32_t v) { uint32_t e = (uint32_t)a; if (__builtin_expect(fm_st_ok(e, 4), 1)) { *(volatile fm_u32*)(b + e) = __builtin_bswap32(v); return; } vm_write32_cold(a, v); }
static inline void fm_wr64(uint8_t* b, uint64_t a, uint64_t v) { uint32_t e = (uint32_t)a; if (__builtin_expect(fm_st_ok(e, 8), 1)) { *(volatile fm_u64*)(b + e) = __builtin_bswap64(v); return; } vm_write64_cold(a, v); }
static inline void fm_raw_ld16(uint8_t* b, void* dst, uint64_t ea) { const uint8_t* p = b + (uint32_t)ea;
    uint64_t lo = *(volatile const uint64_t*)p, hi = *(volatile const uint64_t*)(p + 8); memcpy(dst, &lo, 8); memcpy((uint8_t*)dst + 8, &hi, 8); }
static inline void fm_raw_st16(uint8_t* b, uint64_t ea, const void* src) { uint64_t lo, hi; memcpy(&lo, src, 8); memcpy(&hi, (const uint8_t*)src + 8, 8);
    VM_COH_RAW(ea, 16u, *(volatile uint64_t*)(b + (uint32_t)ea) = lo; *(volatile uint64_t*)(b + (uint32_t)ea + 8) = hi); }
static inline uint8_t  fm_rd8_ng (uint8_t* b, uint64_t a) { return *(volatile const uint8_t*)(b + (uint32_t)a); }
static inline uint16_t fm_rd16_ng(uint8_t* b, uint64_t a) { return __builtin_bswap16(*(volatile const fm_u16*)(b + (uint32_t)a)); }
static inline uint32_t fm_rd32_ng(uint8_t* b, uint64_t a) { return __builtin_bswap32(*(volatile const fm_u32*)(b + (uint32_t)a)); }
static inline uint64_t fm_rd64_ng(uint8_t* b, uint64_t a) { return __builtin_bswap64(*(volatile const fm_u64*)(b + (uint32_t)a)); }
#define vm_read8_ng(a)  fm_rd8_ng(_vmb, (a))
#define vm_read16_ng(a) fm_rd16_ng(_vmb, (a))
#define vm_read32_ng(a) fm_rd32_ng(_vmb, (a))
#define vm_read64_ng(a) fm_rd64_ng(_vmb, (a))
#if FM_LDG == 2
#define FM_DECL uint8_t* const _vmb = fm_base_get(); const uint32_t _vlim = vm_ld_lim, _vref = vm_ld_refp; (void)_vmb; (void)_vlim; (void)_vref;
#define FM_LR _vlim, _vref
#else
#define FM_DECL uint8_t* const _vmb = fm_base_get(); (void)_vmb;
#define FM_LR 0u, 0u
#endif
#undef vm_read8
#undef vm_read16
#undef vm_read32
#undef vm_read64
#undef vm_write8
#undef vm_write16
#undef vm_write32
#undef vm_write64
#define vm_read8(a)  fm_rd8(_vmb, FM_LR, (a))
#define vm_read16(a) fm_rd16(_vmb, FM_LR, (a))
#define vm_read32(a) fm_rd32(_vmb, FM_LR, (a))
#define vm_read64(a) fm_rd64(_vmb, FM_LR, (a))
#define vm_write8(a, v)  fm_wr8(_vmb, (a), (v))
#define vm_write16(a, v) fm_wr16(_vmb, (a), (v))
#define vm_write32(a, v) fm_wr32(_vmb, (a), (v))
#define vm_write64(a, v) fm_wr64(_vmb, (a), (v))
#define vm_raw_ld16(d, ea) fm_raw_ld16(_vmb, (d), (ea))
#define vm_raw_st16(ea, s) fm_raw_st16(_vmb, (ea), (s))
#define vm_base _vmb
/* ---- end fastmem ---- */
''' % (ldg, stg)


HEAD = re.compile(r'^(void func_[0-9A-F]{8}\(ppu_context\* ctx\) \{[^\n]*\n)', re.M)


NG = re.compile(r'\bvm_read(8|16|32|64)\((?=ctx->gpr\[(?:1|2|13)\] \+ )')


def apply(src, ldg=1, stg=1, frame_ng=False):
    """frame_ng: loads addressed off r1 (stack), r2 (TOC) or r13 (small data) take no gate."""
    if frame_ng:
        src = NG.sub(lambda m: f'vm_read{m.group(1)}_ng(', src)
    src = src.replace('#include "ppu_recomp.h"\n', '#include "ppu_recomp.h"\n' + block(ldg, stg), 1)
    return HEAD.sub(lambda m: m.group(1) + '        FM_DECL\n', src)
