#!/usr/bin/env python3
"""T84: find PPU code that builds NV406E semaphore method headers (offline, read-only, private ELF).

Scans every executable PT_LOAD word of generated/decrypted/EBOOT.elf for
  lis rX,<hi>  ...  ori/addi rY,rX,<lo>        (within 8 instructions)
  li rY,<value>                                  (values < 0x8000)
whose 32-bit value is a FIFO method header for subchannel 0 at NV406E_SEMAPHORE_OFFSET (0x64),
_ACQUIRE (0x68) or _RELEASE (0x6C), with count 1 or 2: 0x00040064, 0x00080064, 0x00040068,
0x0004006C, 0x00080068. Also reports such words stored as data. Prints the code addresses.
  py -3 -I scan_sem_headers.py"""
import struct
from pathlib import Path

ELF = Path(__file__).resolve().parents[3] / 'decrypted' / 'EBOOT.elf'
WANT = {0x00040064: 'OFFSET', 0x00080064: 'OFFSET+ACQUIRE', 0x00040068: 'ACQUIRE',
        0x0004006C: 'RELEASE', 0x00080068: 'ACQUIRE+RELEASE'}


def main():
    d = ELF.read_bytes()
    phoff = struct.unpack('>Q', d[0x20:0x28])[0]
    phentsz, phnum = struct.unpack('>HH', d[0x36:0x3a])
    hits = []
    for i in range(phnum):
        t, fl, off, va, pa, fsz, msz, al = struct.unpack('>IIQQQQQQ', d[phoff + i * phentsz:phoff + i * phentsz + 56])
        if t != 1:
            continue
        words = struct.unpack(f'>{fsz // 4}I', d[off:off + fsz // 4 * 4])
        for k, w in enumerate(words):
            a = va + 4 * k
            if w in WANT:
                hits.append((a, 'data-word', WANT[w]))
            if not fl & 1:
                continue
            op = w >> 26
            if op == 14 and (w >> 16) & 31 == 0 and (w & 0xFFFF) in WANT:      # li rD,imm
                hits.append((a, 'li', WANT[w & 0xFFFF]))
            if op == 15 and (w >> 16) & 31 == 0:                                # lis rD,imm
                rd, hi = (w >> 21) & 31, w & 0xFFFF
                for j in range(1, 9):
                    if k + j >= len(words):
                        break
                    x = words[k + j]
                    xo, rs, ra, lo = x >> 26, (x >> 21) & 31, (x >> 16) & 31, x & 0xFFFF
                    if xo == 24 and rs == rd and ((hi << 16) | lo) in WANT:     # ori rA,rS,lo
                        hits.append((a, f'lis/ori @+{4 * j}', WANT[(hi << 16) | lo]))
                    if xo == 14 and ra == rd and ((hi << 16) + (lo - (lo >> 15 << 16))) & 0xFFFFFFFF in WANT:
                        hits.append((a, f'lis/addi @+{4 * j}', WANT[((hi << 16) + (lo - (lo >> 15 << 16))) & 0xFFFFFFFF]))
    for a, how, what in sorted(hits):
        print(f'0x{a:08X}  {how:16s} {what}')
    print(f'total {len(hits)}')


if __name__ == '__main__':
    main()
