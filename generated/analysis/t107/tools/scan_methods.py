"""T107: scan the decrypted EBOOT's executable segments for code that emits
NV4097 methods tied to colour transfer: SHADER_PACKER 0x1FEC and
TEXTURE_ADDRESS 0x1A08+0x20*u. Reports 16-bit immediates (li/addi/ori) and
raw 32-bit header words (count 1..16) anywhere in the file."""
import struct, sys
p = sys.argv[1]
b = open(p, 'rb').read()
e_phoff = struct.unpack('>Q', b[0x20:0x28])[0]; ph_n = struct.unpack('>H', b[0x38:0x3a])[0]
segs = []
for i in range(ph_n):
    o = e_phoff + i * 0x38
    t, fl, off, va, pa, fsz = struct.unpack('>IIQQQQ', b[o:o+0x28])
    if t == 1: segs.append((fl, off, va, fsz))
targets = {0x1FEC: 'SHADER_PACKER'}
for u in range(16): targets[0x1A08 + 0x20*u] = 'TEX%d_ADDRESS' % u
targets[0x1D7C] = 'SHADER_WINDOW?'
for fl, off, va, fsz in segs:
    if not (fl & 1): continue
    for i in range(0, fsz - 3, 4):
        w = struct.unpack('>I', b[off+i:off+i+4])[0]
        op = w >> 26; imm = w & 0xFFFF
        if op in (14, 24) and imm in targets:   # addi/li, ori
            print('code va=0x%X %s %s imm=0x%04X' % (va+i, 'li/addi' if op == 14 else 'ori', targets[imm], imm))
for fl, off, va, fsz in segs:
    for i in range(0, fsz - 3, 4):
        w = struct.unpack('>I', b[off+i:off+i+4])[0]
        m = w & 0xFFFF; c = (w >> 18) & 0x7FF
        if (w & 0xE0030003) == 0 and m in targets and 1 <= c <= 16:
            print('word va=0x%X 0x%08X %s count=%d' % (va+i, w, targets[m], c))
