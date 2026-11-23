"""spunat2: the game-build inputs with the natives (private, game-derived).

  python mkgame.py

  game/wws_reloc/        copy of generated/spu_raw/wws_reloc; groundrush (hand), pvs and screenrush
                         (generated, NAT_EXTRA) lifts get a direct native call at the head of each hooked
                         function and the native source included at the end (the job modules run under
                         the policy module's image id, so the natives are called directly, not through
                         the image-keyed registry)
  game/ovl/lift/         copy of generated/overlays-chain/spu38790/lift, overlay natives (NAT_EXTRA)
  game/spu_native_list.txt  SPU_NATIVE_FILE for the configure-time lift of image 283218738 (hand native)
Every native records entry states with PS3_SPU_FNREC=<dir>; NAT_EXTRA natives run only with
PS3_SPU_NAT2_EXTRA=1; PS3_SPU_NATIVE=0 turns all of them off."""
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parent
ROOT = HERE.parents[3]
NAT = D / 'natives'
G = D / 'game'
W = G / 'wws_reloc'
if W.exists():
    shutil.rmtree(W)
shutil.copytree(ROOT / 'generated/spu_raw/wws_reloc', W)
MODS = [('ms_94e186e6a133_e0D70', 'gr_hand.c', ['0x40D8'], False),
        ('ms_87a63dd45e5d_e2490', 'pvs_gen.c', ['0x5130', '0x54F0', '0x5538'], True),
        ('ms_c99f2f99d2dc_e2640', 'sr_gen.c', ['0x54F0', '0x5460', '0x52F0'], True)]


def patch(path, prefix, native, hooks, extra):
    t = path.read_text(encoding='utf-8')
    decl = ''.join(f'static int nat_{int(h, 0):08X}(spu_context* ctx);\n' for h in hooks)
    first = t.index('\nvoid ')
    t = t[:first] + '\n/* spunat2 natives (see the end of this file) */\n' + decl + t[first:]
    for h in hooks:
        a = int(h, 0)
        head = f'void {prefix}spu_func_{a:08X}(spu_context* ctx) {{\n'
        assert t.count(head) == 1, (path, h)
        t = t.replace(head, head + f'    if (nat_{a:08X}(ctx)) return;   /* spunat2 native */\n')
    t += ('\n/* spunat2 natives */\n' + ('#define NAT_EXTRA 1\n' if extra else '') +
          f'#define LIFT(x) {prefix}##x\n#include "{(NAT / native).as_posix()}"\n#undef LIFT\n')
    path.write_text(t, encoding='utf-8')


for stem, native, hooks, extra in MODS:
    patch(W / stem / 'spu_recomp.c', f'wr_{stem}_', native, hooks, extra)
    print('patched', stem, hooks, native, 'EXTRA' if extra else 'default on')
O = G / 'ovl' / 'lift'
if O.exists():
    shutil.rmtree(O)
shutil.copytree(ROOT / 'generated/overlays-chain/spu38790/lift', O)
patch(O / 'spu_recomp.c', 'local_overlay_bc5bbdfbe5e7_', 'ovl_gen.c', ['0x387F0', '0x36008'], True)
print('patched overlay')
