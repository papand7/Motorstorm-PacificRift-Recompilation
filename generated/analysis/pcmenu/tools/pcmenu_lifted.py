"""PC Settings page: route two lifted calls through the port (port-vkgame/pc_menu.cpp).

  0x00594C10  GUI ExecuteFunction name lookup, both callers (page-load resolver 0x00598468,
              runtime retry 0x0059DF7C) and their linear copies -> pcmenu_lookup(ctx)
  0x001F5DA8  page loader's resource load (bl 0x00752C98, r5 = "gui/<page>.gui") -> pcmenu_page_load(ctx)

Each wrapper calls the original function. Every call line is matched in full and the
counts per file are asserted. Idempotent. A hard-linked file is copied first, so the
trees sharing it keep their bytes. Usage: py -3 pcmenu_lifted.py [staging dir]"""
import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
ST = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'generated' / 'ppu-t173-staging'
DECL = ('extern "C" void pcmenu_lookup(ppu_context* ctx); extern "C" void pcmenu_page_load(ppu_context* ctx);'
        '   /* port pc_menu.cpp: PC Settings page */')
L1 = 'ctx->lr = 0x0059846C; func_00594C10(ctx);'
L2 = 'ctx->lr = 0x0059DF80; func_00594C10(ctx);'
L3 = 'ctx->lr = 0x001F5DAC; func_00752C98(ctx);'
EDITS = {   # file: [(old, new, count)]
    'ppu_recomp_000.cpp': [(L3, L3.replace('func_00752C98', 'pcmenu_page_load'), 1)],
    'ppu_recomp_002.cpp': [(L1, L1.replace('func_00594C10', 'pcmenu_lookup'), 1),
                           (L2, L2.replace('func_00594C10', 'pcmenu_lookup'), 1)],
    'ppu_recomp_009.cpp': [(L3, L3.replace('func_00752C98', 'pcmenu_page_load'), 1)],
    'ppu_recomp_010.cpp': [(L1, L1.replace('func_00594C10', 'pcmenu_lookup'), 1),
                           (L2, L2.replace('func_00594C10', 'pcmenu_lookup'), 1)],
    'ppu_recomp_056.cpp': [(L1, L1.replace('func_00594C10', 'pcmenu_lookup'), 2)],
}

for name, edits in sorted(EDITS.items()):
    path = ST / name
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.pcmenu-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
        print(f'{name}: hard link replaced by a copy')
    s = path.read_bytes().decode('latin-1')
    for old, new, n in edits:
        done, already = s.count(old), s.count(new)
        assert done + already == n, f'{name}: {old} found {done}, patched {already}, want {n}'
        s = s.replace(old, new)
    lines = s.split('\n')
    if DECL not in lines[1] + lines[2] + lines[3]:
        assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
        lines.insert(2, DECL + ('\r' if lines[1].endswith('\r') else ''))
    path.write_bytes('\n'.join(lines).encode('latin-1'))
    print(f'{name}: {sum(n for _, _, n in edits)} calls routed')
