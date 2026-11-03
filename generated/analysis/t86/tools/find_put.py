"""T86: raw-word scan for 'stw rS,0x40(rA)' within 6 words after sync/lwsync/eieio (libgcm PUT publish idiom).
  python find_put.py <start hex> <end hex>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 't84' / 'tools'))
import elf
a0, a1 = int(sys.argv[1], 16), int(sys.argv[2], 16)
BAR = {0x7C0004AC: 'sync', 0x7C2004AC: 'lwsync', 0x7C0006AC: 'eieio'}
last = -100
for a in range(a0, a1, 4):
    w = elf.u32(a)
    if w is None: continue
    if w in BAR: last = a
    elif (w >> 26) == 36 and (w & 0xFFFF) == 0x40 and a - last <= 24:
        print(f'{a:08x} stw r{(w>>21)&31},0x40(r{(w>>16)&31})  barrier {BAR[elf.u32(last)]}@{last:08x}  func~{elf.func_start(a) or 0:08x}')
