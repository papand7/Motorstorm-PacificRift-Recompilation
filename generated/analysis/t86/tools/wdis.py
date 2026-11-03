"""T86: word-by-word PPC disassembly (capstone stops at the first undecodable word; this does not).
  python wdis.py <start hex> <end hex>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 't84' / 'tools'))
import elf, capstone
md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_64 | capstone.CS_MODE_BIG_ENDIAN)
a0, a1 = int(sys.argv[1], 16), int(sys.argv[2], 16)
for a in range(a0, a1, 4):
    b = elf.rd(a, 4)
    ins = list(md.disasm(b, a)) if b else []
    print(f'{a:08x}  {(elf.u32(a) or 0):08x}  ' + (f'{ins[0].mnemonic:8s} {ins[0].op_str}' if ins else '.word'))
