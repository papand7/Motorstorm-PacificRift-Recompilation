"""T140: stage ppu_loader.cpp in steps so each commit holds one change (the working tree keeps the final file).

  python -I stage_split.py <tree> fast    # store fast path + PS3_VM_STATS, without the two below
  python -I stage_split.py <tree> resv    # + PPU_RESV_STORE on lifted stores
  python -I stage_split.py <tree> full    # + raw-store coherence entry points (the working-tree file)
"""
import subprocess
import sys
from pathlib import Path

tree, step = Path(sys.argv[1]), sys.argv[2]
rel = 'runtime/ppu/ppu_loader.cpp'
s = (tree / rel).read_bytes().decode('utf-8').replace('\r\n', '\n')

RESV = [
    ('    static const char* const vars[] = { "PPU_WVAL", "PPU_WWATCH", "PT", "PPU_RESV_STORE", 0 };\n',
     '    static const char* const vars[] = { "PPU_WVAL", "PPU_WWATCH", "PT", 0 };\n'),
    (' *   - g_vm_store_slow: the environment-armed probes (PPU_WVAL, PPU_WWATCH, PT,\n'
     ' *     PPU_RESV_STORE, PS3_VM_STATS). -1 until the first store reads them, so\n',
     ' *   - g_vm_store_slow: the environment-armed probes (PPU_WVAL, PPU_WWATCH, PT,\n'
     ' *     PS3_VM_STATS). -1 until the first store reads them, so\n'),
    ('      /* PPU_RESV_STORE=1: a plain store breaks the other threads\' reservations\n'
     '       * on the word, as the HLE writers in ppu_memory.h already did. Lifted\n'
     '       * stores come here, and before T140 they never did: the switch covered\n'
     '       * libs/ only. */\n'
     '      if (g_resv_store_active > 0) ppu_resv_break_store(a);\n', ''),
    ('    v = __builtin_bswap64(v); VM_WRITE_COH(a, &v, 8);\n'
     '    /* PPU_RESV_STORE=1: both words of the doubleword (reservations are kept\n'
     '     * per word here). */\n'
     '    if (g_resv_store_active > 0) { ppu_resv_break_store(a); ppu_resv_break_store(a + 4); } }\n',
     '    v = __builtin_bswap64(v); VM_WRITE_COH(a, &v, 8); }\n'),
]


def cut_raw(t):
    a = t.index('/* Raw (guest byte order) stores from lifted code -- stvx, stvebx/ehx/ewx,')
    b = t.index('    vm_stat(VMS_RAW_COH);\n    spu_lockline_unlock();\n}\n', a)
    b += len('    vm_stat(VMS_RAW_COH);\n    spu_lockline_unlock();\n}\n')
    return t[:a].rstrip('\n') + '\n' + t[b:]


def undo(t, pairs):
    for new, old in pairs:
        assert t.count(new) == 1, new[:70]
        t = t.replace(new, old)
    return t


if step in ('fast', 'resv'):
    s = cut_raw(s)
if step == 'fast':
    s = undo(s, RESV)
data = s.replace('\n', '\r\n').encode('utf-8')
oid = subprocess.run(['git', '-C', str(tree), 'hash-object', '-w', '--stdin', '--path=' + rel], input=data,
                     capture_output=True, check=True).stdout.decode().strip()
subprocess.run(['git', '-C', str(tree), 'update-index', '--cacheinfo', f'100644,{oid},{rel}'], check=True)
print('staged', step, oid[:10])
