#!/usr/bin/env python3
"""T85: list direct branch callers (b/bl, relative) of guest addresses in the retail ELF text (offline).
Also reports 32-bit words equal to the target (function descriptors / vtables point at descriptors,
so descriptor addresses are reported too).  python blscan.py <target hex> [...]"""
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 't84' / 'tools'))
import elf


def main(targets):
    tg = set(targets)
    for va, off, fsz, fl in elf.SEGS:
        words = struct.unpack(f'>{fsz // 4}I', elf.D[off:off + fsz // 4 * 4])
        for i, w in enumerate(words):
            a = va + 4 * i
            if fl & 1 and w >> 26 == 18:
                li = w & 0x03FFFFFC
                if li & 0x02000000:
                    li -= 0x04000000
                t = li if w & 2 else a + li
                if t in tg:
                    print(f'{a:08x} {"bl" if w & 1 else "b "} -> {t:08x}')
            if w in tg:
                print(f'{a:08x} word  = {w:08x}  (seg flags {fl})')


if __name__ == '__main__':
    main([int(x, 16) for x in sys.argv[1:]])
