"""Verify the func_00CB7D80 jump table straight from the ELF: TOC slot, 29 offset entries, bounds, in-function targets.
usage: table_t173.py <elf> <ps3recomp tools dir>"""
import struct, sys

sys.path.insert(0, sys.argv[2])
import ppu_disasm

d = open(sys.argv[1], 'rb').read()
phoff, phes, phn = struct.unpack('>Q', d[32:40])[0], *struct.unpack('>HH', d[54:58])
SEG = []
for i in range(phn):
    t, fl, off, va, _, fsz, _, _ = struct.unpack('>IIQQQQQQ', d[phoff + i * phes:phoff + i * phes + 56])
    if t == 1:
        SEG.append((va, off, fsz, fl))


def rd(a):
    for va, off, fsz, _ in SEG:
        if va <= a < va + fsz:
            return struct.unpack('>I', d[off + a - va:off + a - va + 4])[0]


R2, FN_LO, FN_HI = 0x010CE894, 0xCB7D80, 0xCB9458   # r2 from the crash dump; function bounds from the lifted source
slot = R2 + 0x65D8
base = rd(slot)
print(f'TOC slot r2+0x65D8 = 0x{slot:08X} -> 0x{base:08X}')
tg = []
for k in range(29):
    v = rd(base + 4 * k)
    s = v - (1 << 32) if v & 0x80000000 else v
    t = (base + s) & 0xFFFFFFFF
    tg.append(t)
    w = rd(t)
    ok = FN_LO <= t < FN_HI and t % 4 == 0
    print(f'case {k:2d} entry@{base + 4 * k:08X}={v:08X} -> {t:08X} in_fn={ok} insn={ppu_disasm.decode(w, t).mnemonic}')
print('word after table', hex(base + 29 * 4), f'{rd(base + 29 * 4):08X}', '=', ppu_disasm.decode(rd(base + 116), base + 116).mnemonic)
print('distinct targets', len(set(tg)), 'default (loop head 0xCB7E48) entries', tg.count(0xCB7E48))
print('selector 1 (r9=4) ->', hex(tg[1]))
