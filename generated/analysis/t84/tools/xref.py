#!/usr/bin/env python3
"""T84B: code references to guest addresses in the retail ELF (offline, read-only).
For each address: TOC slots holding it, instructions loading such a slot as lwz rD,d(r2) for both
TOC bases (main 0x109FBF0, engine 0x10AFBE4), and lis/addi|ori pairs building it within 8 words.
Also direct branches when the address is code.
  py -3 -I xref.py <hex addr> [...]"""
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import elf

TOCS = (0x0109FBF0, 0x010AFBE4)


def xref(target):
    slots = [a for a in elf.find_word(target) if a >= 0x01000000]
    hits = []
    for seg in elf.TEXT:
        va, ws = elf.words(seg)
        for k, w in enumerate(ws):
            op = w >> 26
            if op == 32 and (w >> 16) & 31 == 2:                       # lwz rD,d(r2)
                d = w & 0xFFFF
                d = d - 0x10000 if d & 0x8000 else d
                for t in TOCS:
                    if t + d in slots:
                        hits.append((va + 4 * k, f'lwz toc{t:X}{d:+#x}'))
            if op == 15 and (w >> 16) & 31 == 0:                       # lis rD,hi
                rd, hi = (w >> 21) & 31, w & 0xFFFF
                for j in range(1, 9):
                    if k + j >= len(ws):
                        break
                    x = ws[k + j]
                    xo, rs, ra, lo = x >> 26, (x >> 21) & 31, (x >> 16) & 31, x & 0xFFFF
                    if xo == 14 and ra == rd and ((hi << 16) + (lo - 0x10000 if lo & 0x8000 else lo)) & 0xFFFFFFFF == target:
                        hits.append((va + 4 * k, f'lis/addi +{4 * j}'))
                    if xo == 24 and rs == rd and ((hi << 16) | lo) == target:
                        hits.append((va + 4 * k, f'lis/ori +{4 * j}'))
    br = elf.branches_to([target])[target]
    return slots, hits, br


if __name__ == '__main__':
    for a in sys.argv[1:]:
        t = int(a, 16)
        slots, hits, br = xref(t)
        print(f'0x{t:08X}: slots {[hex(s) for s in slots]}')
        for site, how in hits:
            print(f'   0x{site:08X} {how}   fn~0x{(elf.func_start(site) or 0):08X}')
        for site, how in br:
            print(f'   0x{site:08X} {how}       fn~0x{(elf.func_start(site) or 0):08X}')
