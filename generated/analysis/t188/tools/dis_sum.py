MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
import sys, subprocess
from pathlib import Path
sys.path.insert(0, (MS_ROOT + r'\ps3recomp-t188\tools'))
import ppu_difftest as D, ppu_regpromo as rp, bench_ppu_regpromo as B
p = D.kernel_program(['sum']); h, s = D.lift(p, False)
out = Path((MS_ROOT + r'\generated\analysis\t188\scratch\dis_sum'))
for v, src in (('base', s), ('promo', rp.promote_source(s))):
    exe, ct, osz = D.build(out, v, h, src, p)
    o = subprocess.run([B.objdump(), '-d', '--no-show-raw-insn', '-M', 'intel', '--disassemble-symbols=?func_00010000@@YAXPEAUppu_context@@@Z', str(exe.parent / 'lifted.obj')], capture_output=True, text=True).stdout
    (out / f'{v}.asm').write_text(o)
    print(v, len([l for l in o.splitlines() if l.startswith('  ')]))
