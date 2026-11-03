"""T140: lifter -- raw (vector / byte-reversed / dcbz) stores take the coherent path on an SPU-reserved line
when the runtime arms it (PPU_RAW_STORE_COH=1). Edits tools/ppu_lifter.py and tools/test_ppu_lift.py."""
import sys
from pathlib import Path

W = Path(sys.argv[1])


def edit(rel, pairs):
    p = W / rel
    s = p.read_bytes().decode('utf-8')
    crlf = '\r\n' in s
    s = s.replace('\r\n', '\n')
    for old, new in pairs:
        assert s.count(old) == 1, (rel, old[:80], s.count(old))
        s = s.replace(old, new)
    if crlf:
        s = s.replace('\n', '\r\n')
    p.write_bytes(s.encode('utf-8'))
    print('edited', rel)


BS = '\\'   # a line-continuation backslash inside the lifter's (non-raw) header string

edit('tools/ppu_lifter.py', [
    ('#define VM_RAW_ST(T, ea, val) do { uint8_t* _p = vm_base + (uint32_t)(ea); T _v = (val); \\\n'
     '    if (!((uintptr_t)_p & (sizeof(T) - 1))) __atomic_store_n((T*)_p, _v, __ATOMIC_RELAXED); \\\n'
     '    else memcpy(_p, &_v, sizeof(T)); } while (0)\n',
     '#define VM_RAW_ST_PLAIN(T, ea, val) do { uint8_t* _p = vm_base + (uint32_t)(ea); T _v = (val); \\\n'
     '    if (!((uintptr_t)_p & (sizeof(T) - 1))) __atomic_store_n((T*)_p, _v, __ATOMIC_RELAXED); \\\n'
     '    else memcpy(_p, &_v, sizeof(T)); } while (0)\n'
     '/* Raw stores and SPU lock-line coherence. The scalar stores go through\n'
     ' * vm_write*, which serialize a store to an SPU-reserved 128-byte line with\n'
     ' * the SPU lock-line lock and raise the SPU\'s lost-reservation event; the raw\n'
     ' * forms (stvx, stvebx/ehx/ewx, stvlx/rx, stwbrx/sthbrx/stdbrx, dcbz) store\n'
     ' * here and used to skip both. The runtime sets g_ppu_raw_coh (opt-in,\n'
     ' * PPU_RAW_STORE_COH=1, and only once an SPU has reserved a line); then a\n'
     ' * store whose first or last byte lies on a reserved line is bracketed by\n'
     ' * vm_raw_coh_begin/end. Off, it costs one load and an untaken branch.\n'
     ' * PPU_NO_RAW_STORE_COH compiles the test out. */\n'
     'extern int g_ppu_raw_coh;\n'
     'extern unsigned char g_spu_coh_bitmap[];\n'
     'void vm_raw_coh_begin(void);\n'
     'void vm_raw_coh_end(uint64_t ea, uint32_t n);\n'
     'static inline int vm_raw_coh_hit(uint64_t ea, uint32_t n) {\n'
     '    if (__builtin_expect(!g_ppu_raw_coh, 1)) return 0;\n'
     '    const uint32_t a = (uint32_t)ea, e = a + n - 1u;\n'
     '    return ((g_spu_coh_bitmap[a >> 10] >> ((a >> 7) & 7u)) |\n'
     '            (g_spu_coh_bitmap[e >> 10] >> ((e >> 7) & 7u))) & 1u; }\n'
     '#ifdef PPU_NO_RAW_STORE_COH\n'
     '#define VM_COH_RAW(ea, n, ...) do { __VA_ARGS__; } while (0)\n'
     '#else\n'
     '#define VM_COH_RAW(ea, n, ...) do { const uint64_t _cea = (ea); \\\n'
     '    if (__builtin_expect(vm_raw_coh_hit(_cea, (n)), 0)) { vm_raw_coh_begin(); __VA_ARGS__; vm_raw_coh_end(_cea, (n)); } \\\n'
     '    else { __VA_ARGS__; } } while (0)\n'
     '#endif\n'
     '#define VM_RAW_ST(T, ea, val) do { const uint64_t _sea = (ea); const T _sv = (val); \\\n'
     '    VM_COH_RAW(_sea, (uint32_t)sizeof(T), VM_RAW_ST_PLAIN(T, _sea, _sv)); } while (0)\n'),
    ('static inline void vm_raw_st16(uint64_t ea, const void* src) {\n'
     '    uint64_t lo, hi; memcpy(&lo, src, 8); memcpy(&hi, (const uint8_t*)src + 8, 8);\n'
     '    VM_RAW_ST(uint64_t, ea, lo); VM_RAW_ST(uint64_t, ea + 8, hi); }\n',
     'static inline void vm_raw_st16(uint64_t ea, const void* src) {   /* quadword-aligned */\n'
     '    uint64_t lo, hi; memcpy(&lo, src, 8); memcpy(&hi, (const uint8_t*)src + 8, 8);\n'
     '    VM_COH_RAW(ea, 16u, VM_RAW_ST_PLAIN(uint64_t, ea, lo); VM_RAW_ST_PLAIN(uint64_t, ea + 8, hi)); }\n'),
    ('            return (f"{{ uint64_t ea = {_xea(ra, rb)}; uint32_t sh = (uint32_t)(ea & 0xF); "\n'
     '                    f"uint8_t* m = vm_base + (uint32_t)(ea & ~0xFULL); "\n'
     '                    f"const uint8_t* s = (const uint8_t*)&ctx->vr[{vs}]; {loop} }}")\n',
     '            # The bytes stay inside EA\'s quadword, so one line decides coherence.\n'
     '            return (f"{{ uint64_t ea = {_xea(ra, rb)}; uint32_t sh = (uint32_t)(ea & 0xF); "\n'
     '                    f"uint8_t* m = vm_base + (uint32_t)(ea & ~0xFULL); "\n'
     '                    f"const uint8_t* s = (const uint8_t*)&ctx->vr[{vs}]; "\n'
     '                    f"VM_COH_RAW(ea & ~0xFULL, 16u, {loop}); }}")\n'),
    ('            return (f"{{ uint64_t ea = ({_xea(ra,rb)}) & ~0x7FULL; "\n'
     '                    f"memset(vm_base + (uint32_t)ea, 0, 128); }}")\n',
     '            # A store to the whole line: coherent like any other store to it.\n'
     '            return (f"{{ uint64_t ea = ({_xea(ra,rb)}) & ~0x7FULL; "\n'
     '                    f"VM_COH_RAW(ea, 128u, memset(vm_base + (uint32_t)ea, 0, 128)); }}")\n'),
])

edit('tools/test_ppu_lift.py', [
    ('#define VM_RAW_ST(T, ea, val) do { T _v = (val); memcpy(g_vm_stub + VMOFF(ea), &_v, sizeof(T)); } while (0)\n',
     '#define VM_RAW_ST(T, ea, val) do { T _v = (val); memcpy(g_vm_stub + VMOFF(ea), &_v, sizeof(T)); } while (0)\n'
     '/* No SPU here: the coherence bracket around raw stores is the plain store. */\n'
     '#define VM_COH_RAW(ea, n, ...) do { __VA_ARGS__; } while (0)\n'),
])
