"""T107: disassemble EBOOT ranges: dis.py <elf> <va_start_hex> <va_end_hex>."""
import struct, sys, capstone
b = open(sys.argv[1], 'rb').read()
lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
phoff = struct.unpack('>Q', b[0x20:0x28])[0]; n = struct.unpack('>H', b[0x38:0x3a])[0]
md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_64 | capstone.CS_MODE_BIG_ENDIAN)
for i in range(n):
    o = phoff + i * 0x38
    t, fl, off, va, pa, fsz = struct.unpack('>IIQQQQ', b[o:o+0x28 + 8][:0x28]) if False else struct.unpack('>IIQQQQ', b[o:o+0x28])
    if t != 1 or not (va <= lo < va + fsz): continue
    for ins in md.disasm(b[off + lo - va: off + min(hi, va + fsz) - va], lo):
        print('%08X  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))
