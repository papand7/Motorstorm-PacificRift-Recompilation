#!/usr/bin/env python3
"""T85: find D-form loads/stores/addi with a given displacement in the retail ELF text (offline, read-only).
Prints address, mnemonic class, rD, rA and the nearest preceding 'stdu r1,..(r1)' (function start guess).
  python dscan.py <disp hex> [<disp hex> ...]"""
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 't84' / 'tools'))
import elf

OPS = {14: 'addi', 32: 'lwz', 33: 'lwzu', 34: 'lbz', 36: 'stw', 37: 'stwu', 38: 'stb', 40: 'lhz', 44: 'sth', 48: 'lfs', 52: 'stfs', 58: 'ld', 62: 'std'}


def main(disps):
    want = {d & 0xFFFF for d in disps}
    for va, off, fsz, _ in elf.TEXT:
        words = struct.unpack(f'>{fsz // 4}I', elf.D[off:off + fsz // 4 * 4])
        start = None
        for i, w in enumerate(words):
            op = w >> 26
            if w & 0xFFFF0000 == 0xF8210000 or (op == 62 and (w >> 16) & 0x3FF == 0x21 and w & 3 == 1):
                start = va + 4 * i                     # stdu r1,-x(r1)
            if op in OPS and (w & 0xFFFF) in want:
                d = w & 0xFFFF
                if op in (58, 62):
                    d &= 0xFFFC
                    if d not in want:
                        continue
                rd, ra = (w >> 21) & 31, (w >> 16) & 31
                if ra in (1, 2):
                    continue
                print(f'{va + 4 * i:08x} {OPS[op]:5s} r{rd}, 0x{d:x}(r{ra})   fn~{start or 0:08x}')


if __name__ == '__main__':
    main([int(a, 16) for a in sys.argv[1:]])
