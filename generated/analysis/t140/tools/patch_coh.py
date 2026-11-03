"""T140: export the SPU reserved-line bitmap for inline PPU store checks; PPU_RAW_STORE_COH gate."""
import sys
from pathlib import Path

W = Path(sys.argv[1])


def edit(rel, pairs):
    p = W / rel
    s = p.read_bytes().decode('utf-8')
    crlf = '\r\n' in s
    s = s.replace('\r\n', '\n')
    for old, new in pairs:
        assert s.count(old) == 1, (rel, old[:70], s.count(old))
        s = s.replace(old, new)
    if crlf:
        s = s.replace('\n', '\r\n')
    p.write_bytes(s.encode('utf-8'))
    print('edited', rel)


edit('runtime/spu/spu_coherency.c', [
    ('static unsigned char s_coh_bitmap[SPU_COH_BITMAP_SZ];\n',
     '/* Exported (spu_coherency.h): the PPU store paths test a line inline instead\n'
     ' * of calling spu_coh_is_reserved for every guest store. */\n'
     'unsigned char g_spu_coh_bitmap[SPU_COH_BITMAP_SZ];\n'),
    ('static int s_coh_armed;\n',
     'int g_spu_coh_armed;\n'
     '\n'
     '/* PPU_RAW_STORE_COH=1: the lifted raw stores (stvx, stvebx/ehx/ewx, stvlx/rx,\n'
     ' * stwbrx/sthbrx/stdbrx, dcbz) also take the coherent path on a reserved line.\n'
     ' * Set with g_spu_coh_armed, so it is 0 until a line is reserved. */\n'
     'int g_ppu_raw_coh;\n'),
    ('    s_coh_bitmap[line >> 3] |= (unsigned char)(1u << (line & 7));\n    s_coh_armed = 1;\n',
     '    g_spu_coh_bitmap[line >> 3] |= (unsigned char)(1u << (line & 7));\n'
     '    if (!g_spu_coh_armed) {\n'
     '        const char* e = getenv("PPU_RAW_STORE_COH");\n'
     '        g_ppu_raw_coh = (e && *e && *e != \'0\') ? 1 : 0;\n'
     '    }\n'
     '    g_spu_coh_armed = 1;\n'),
    ('    if (!s_coh_armed) return 0;\n    uint32_t line = addr >> SPU_COH_LINE_SHIFT;\n'
     '    return (s_coh_bitmap[line >> 3] >> (line & 7)) & 1u;\n',
     '    return spu_coh_line_marked(addr);\n'),
])

edit('runtime/spu/spu_coherency.h', [
    ('int spu_coh_is_reserved(uint32_t addr);\n',
     'int spu_coh_is_reserved(uint32_t addr);\n'
     '\n'
     '/* The same test, inline: one bit per 128-byte line of the 32-bit space\n'
     ' * (4 MiB), and the flag that stays 0 until the first reservation. Bits are\n'
     ' * only ever set, so a line seen marked stays marked. */\n'
     'extern unsigned char g_spu_coh_bitmap[];\n'
     'extern int g_spu_coh_armed;\n'
     'extern int g_ppu_raw_coh;   /* PPU_RAW_STORE_COH, see spu_coherency.c */\n'
     'static inline int spu_coh_line_marked(uint32_t addr)\n'
     '{\n'
     '    return g_spu_coh_armed && ((g_spu_coh_bitmap[addr >> 10] >> ((addr >> 7) & 7u)) & 1u);\n'
     '}\n'),
])
