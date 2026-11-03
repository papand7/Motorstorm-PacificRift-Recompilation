"""Disassemble a guest address range from the decrypted ELF with the lifter's own decoder (ps3recomp tools/ppu_disasm.py).
usage: dump_func_t173.py <ps3recomp tools dir> <elf> <hex start> <hex end> [mnemonic-substring filter]"""
import struct, sys

sys.path.insert(0, sys.argv[1])
import ppu_disasm

d = open(sys.argv[2], 'rb').read()
lo, hi = int(sys.argv[3], 16), int(sys.argv[4], 16)
flt = sys.argv[5] if len(sys.argv) > 5 else ''
phoff, phes, phn = struct.unpack('>Q', d[32:40])[0], *struct.unpack('>HH', d[54:58])
for i in range(phn):
    t, fl, off, va, _, fsz, _, _ = struct.unpack('>IIQQQQQQ', d[phoff + i * phes:phoff + i * phes + 56])
    if t == 1 and va <= lo < va + fsz:
        for a in range(lo, hi, 4):
            w = struct.unpack('>I', d[off + a - va:off + a - va + 4])[0]
            ins = ppu_disasm.decode(w, a)
            line = f'{a:08X}: {w:08X}  {ins.mnemonic} {ins.operands}'
            if flt in line:
                print(line)
        break
