"""T140: inline SPU-line test in the store fast path; coherent store helper; raw-store entry points."""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'runtime/ppu/ppu_loader.cpp'
s = p.read_bytes().decode('utf-8').replace('\r\n', '\n')


def sub(old, new):
    global s
    assert s.count(old) == 1, (old[:80], s.count(old))
    s = s.replace(old, new)


sub('''extern "C" int g_vm_store_slow = -1;
static int vm_stats_on(void);
''', '''extern "C" int g_vm_store_slow = -1;
static int vm_stats_on(void);

/* The SPU reserved-line bitmap (spu_coherency.c), tested inline. Fixtures that
 * link this loader without the SPU runtime -- and stub spu_coh_is_reserved to
 * 0 -- get an unarmed default instead of an undefined symbol. */
#if defined(_MSC_VER)
extern "C" int g_spu_coh_armed;
extern "C" unsigned char g_spu_coh_bitmap[];
extern "C" int g_spu_coh_armed_absent = 0;
extern "C" unsigned char g_spu_coh_bitmap_absent[1] = { 0 };
#pragma comment(linker, "/alternatename:g_spu_coh_armed=g_spu_coh_armed_absent")
#pragma comment(linker, "/alternatename:g_spu_coh_bitmap=g_spu_coh_bitmap_absent")
#else
extern "C" __attribute__((weak)) int g_spu_coh_armed = 0;
extern "C" __attribute__((weak)) unsigned char g_spu_coh_bitmap[1u << 22];
#endif
/* spu_coh_is_reserved, inline: same flag, same bit. */
static inline int vm_coh_marked(uint32_t a)
{
    return __builtin_expect(g_spu_coh_armed, 0) && ((g_spu_coh_bitmap[a >> 10] >> ((a >> 7) & 7u)) & 1u);
}
/* VM_WRITE_COH's reserved branch, out of line: the store under the lock-line
 * lock, then the lost-reservation notify for the line. */
static __attribute__((noinline)) void vm_store_coh(uint32_t a, const void* raw, size_t n)
{
    spu_lockline_lock();
    memcpy(vm_base + a, raw, n);
    spu_coh_notify_write(a);
    spu_lockline_unlock();
}
''')

old_fast = s[s.index('void vm_write8 (uint64_t a, uint8_t  v)\n{\n    if (vm_store_fast_ok'):]
old_fast = old_fast[:old_fast.index('    vm_write64_full(a, v, __builtin_return_address(0));\n}\n') +
                    len('    vm_write64_full(a, v, __builtin_return_address(0));\n}\n')]
sub(old_fast, '''void vm_write8 (uint64_t a, uint8_t  v)
{
    if (vm_store_fast_ok((uint32_t)a)) {
        if (__builtin_expect(!vm_coh_marked((uint32_t)a), 1)) { vm_base[(uint32_t)a] = v; return; }
        vm_store_coh((uint32_t)a, &v, 1); return; }
    vm_write8_full(a, v, __builtin_return_address(0));
}
void vm_write16(uint64_t a, uint16_t v)
{
    if (vm_store_fast_ok((uint32_t)a)) {
        const uint16_t raw = __builtin_bswap16(v);
        if (__builtin_expect(!vm_coh_marked((uint32_t)a), 1)) { memcpy(vm_base + (uint32_t)a, &raw, 2); return; }
        vm_store_coh((uint32_t)a, &raw, 2); return; }
    vm_write16_full(a, v, __builtin_return_address(0));
}
void vm_write32(uint64_t a, uint32_t v)
{
    if (vm_store_fast_ok((uint32_t)a) && !spu_raw_is_reg((uint32_t)a)) {
        const uint32_t raw = __builtin_bswap32(v);
        if (__builtin_expect(!vm_coh_marked((uint32_t)a), 1)) { memcpy(vm_base + (uint32_t)a, &raw, 4); return; }
        vm_store_coh((uint32_t)a, &raw, 4); return; }
    vm_write32_full(a, v, __builtin_return_address(0));
}
void vm_write64(uint64_t a, uint64_t v)
{
    if (vm_store_fast_ok((uint32_t)a)) {
        const uint64_t raw = __builtin_bswap64(v);
        if (__builtin_expect(!vm_coh_marked((uint32_t)a), 1)) { memcpy(vm_base + (uint32_t)a, &raw, 8); return; }
        vm_store_coh((uint32_t)a, &raw, 8); return; }
    vm_write64_full(a, v, __builtin_return_address(0));
}

/* Raw (guest byte order) stores from lifted code -- stvx, stvebx/ehx/ewx,
 * stvlx/stvrx, stwbrx/sthbrx/stdbrx, dcbz -- store straight into guest memory
 * (VM_RAW_ST in ppu_recomp.h) and never reached the lock-line serialization or
 * the lost-reservation notify the scalar stores get (T131). With
 * PPU_RAW_STORE_COH=1 (g_ppu_raw_coh) the generated code tests the line(s)
 * inline and, on a reserved one, brackets its store with these two calls:
 * begin takes the lock-line lock, end notifies every reserved 128-byte line
 * in [ea, ea + n) and releases it. Same order as VM_WRITE_COH: store, notify,
 * unlock. */
void vm_raw_coh_begin(void)
{
    spu_lockline_lock();
}
void vm_raw_coh_end(uint64_t ea, uint32_t n)
{
    const uint32_t first = (uint32_t)ea & ~127u, last = ((uint32_t)ea + (n ? n - 1u : 0u)) & ~127u;
    for (uint32_t line = first; ; line += 128u) {
        if (vm_coh_marked(line)) spu_coh_notify_write(line);
        if (line == last) break;
    }
    vm_stat(VMS_RAW_COH);
    spu_lockline_unlock();
}
''')
p.write_bytes(s.replace('\n', '\r\n').encode('utf-8'))
print('ok')
