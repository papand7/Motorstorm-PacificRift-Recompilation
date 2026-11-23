"""PC Settings page on 1.03: route three lifted spots through the port (port-vkgame/pc_menu.cpp,
the PORT_V103 branch). The 1.02 sites (pcmenu_lifted.py) are different addresses.

  func_005604C8  GUI ExecuteFunction name lookup (1.02 func_00594C10; found by instruction shape,
                 callers 0x00561DA4 and 0x00564214, 666 = 0x29A "no such function" in it)
                 both callers -> pcmenu_lookup(ctx)             [ppu_recomp_001.cpp]
  func_00503718  resource load (1.02 0x00536A30 LoadSync, unique match of find_sites_103.py); the
                 trampoline func_0071C408 tail-branches to it -> pcmenu_load_sync   [ppu_recomp_002.cpp]

Each wrapper calls the original function. Every line is matched in full and the count per file is
asserted. Idempotent. DRY RUN unless --apply (the staging folder is read by builds: only apply it
when none is running, then rebuild ppu_recomp_001/002 and relink).

usage: py -3 pcmenu_lifted_103.py [--apply] [staging dir (default generated/ppu-v103-staging)]"""
import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
args = [a for a in sys.argv[1:] if not a.startswith('--')]
APPLY = '--apply' in sys.argv
ST = pathlib.Path(args[0]) if args else ROOT / 'generated' / 'ppu-v103-staging'
DECL = ('extern "C" void pcmenu_lookup(ppu_context* ctx); extern "C" void pcmenu_load_sync(void* ctx);'
        '   /* port pc_menu.cpp: PC Settings page */')
L1 = 'ctx->lr = 0x00561DA4; func_005604C8(ctx);'
L2 = 'ctx->lr = 0x00564214; func_005604C8(ctx);'
T1 = '{ g_trampoline_fn = (void(*)(void*))func_00503718; return; }'
EDITS = {   # file: [(old, new, count)]
    'ppu_recomp_001.cpp': [(L1, L1.replace('func_005604C8', 'pcmenu_lookup'), 1),
                           (L2, L2.replace('func_005604C8', 'pcmenu_lookup'), 1)],
    'ppu_recomp_002.cpp': [(T1, T1.replace('func_00503718', 'pcmenu_load_sync'), 1)],
}

for name, edits in sorted(EDITS.items()):
    path = ST / name
    s = path.read_bytes().decode('latin-1')
    for old, new, n in edits:
        done, already = s.count(old), s.count(new)
        assert done + already == n, f'{name}: {old} found {done}, patched {already}, want {n}'
        s = s.replace(old, new)
    lines = s.split('\n')
    if DECL not in '\n'.join(lines[:6]):
        assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
        lines.insert(2, DECL + ('\r' if lines[1].endswith('\r') else ''))
    n_edit = sum(n for _, _, n in edits)
    if not APPLY:
        print(f'{name}: {n_edit} spot(s) match (dry run, nothing written)')
        continue
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.pcmenu-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
        print(f'{name}: hard link replaced by a copy')
    path.write_bytes('\n'.join(lines).encode('latin-1'))
    print(f'{name}: {n_edit} spot(s) routed')
