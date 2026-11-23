MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
def edit(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert s.count(a) == 1, (p, a, s.count(a))
        s = s.replace(a, b)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)


T = (MS_ROOT + r'\ps3recomp-t189\tools\ppu_difftest.py')
edit(T, [
    ('''    (d / "ppu_recomp.h").write_text(header + INLINE_STORES, encoding="utf-8")''',
     '''    # inline stores: the lifter header's own (T152) block; INLINE_STORES only for older headers
    extra_hdr = "" if "vm_write32_inl" in header else INLINE_STORES
    (d / "ppu_recomp.h").write_text(header + extra_hdr, encoding="utf-8")'''),
    ('''volatile uint8_t vm_st_page[65536];\nint vm_st_inline = 1;''',
     '''volatile uint8_t vm_st_page[65536];\nuint8_t vm_ld_page[65536];\nint vm_st_inline = 1;'''),
    ('''for (uint32_t p = 1; p < (MEM_SIZE >> 16); p++) vm_st_page[p] = 1;''',
     '''for (uint32_t p = 1; p < (MEM_SIZE >> 16) && p < 65536; p++) vm_st_page[p] = vm_ld_page[p] = 1;'''),
])

R = (MS_ROOT + r'\generated\analysis\t188\tools\real_bench.py')
s = open(R, encoding='utf-8').read()
a0 = s.index("    blk = hp[hp.index('/* PPU_COLD_CALLS'):")
a1 = s.index("    hdr = hdr.replace('\\r\\n', '\\n')")
new = '''    blk = hp[hp.index('/* T152 page gates: begin */'):hp.index('/* T152 page gates: end */') + 26] + '\\n'
    hdr = hdr.replace('\\r\\n', '\\n')
    old = ('#ifdef __cplusplus\\n}\\n#endif\\nstatic inline int vm_inl_ok(uint32_t ea, uint32_t n)\\n{\\n'
           '    return __builtin_expect(vm_inline_ok, 1) && ea >= 0x10000u && ea < 0xE0000000u &&\\n'
           '           ea != ppu_hle_inject_base + 0x2008u &&\\n'
           '           (ppu_vm_size == 0 || (uint64_t)ea + n <= ppu_vm_size);\\n}\\n')
    assert hdr.count(old) == 1
    # the current lifter's T152 block: page gates, cold thunks, inline stores (all macro-selected)
    hdr = hdr.replace(old, blk)   # blk closes the extern "C" block as `old` did
'''
s = s[:a0] + new + s[a1:]
open(R, 'w', encoding='utf-8', newline='\n').write(s)
print('ok')
