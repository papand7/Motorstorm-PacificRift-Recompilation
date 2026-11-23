"""Find the 1.03 address of a 1.02 function by instruction shape: every word is compared on
its top 16 bits only (opcode + registers; immediates, branch displacements and TOC offsets
ignored), over the first N words of the function. Prints every 1.03 hit.
usage: py -3 find103.py <hex addr> [N=40]"""
import pathlib, struct, sys
R = pathlib.Path(__file__).resolve().parents[4]


def segs(p):
    b = p.read_bytes()
    phoff, = struct.unpack_from('>Q', b, 0x20)
    phn, = struct.unpack_from('>H', b, 0x38)
    out = []
    for i in range(phn):
        t, fl, off, va, pa, fs, ms, al = struct.unpack_from('>IIQQQQQQ', b, phoff + 56 * i)
        if t == 1 and fl & 1:
            out.append((va, struct.unpack(f'>{fs // 4}I', b[off:off + fs // 4 * 4])))
    return out


def sh16(x):
    return x >> 26


def _old(x):
    return ((x & 0xFC000003) >> 16) if x >> 26 == 18 else x >> 16


A = segs(R / 'generated/decrypted/EBOOT.elf')
B = segs(R / 'generated/decrypted/v103/EBOOT_103.elf')
va = int(sys.argv[1], 16)
n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
pat = None
for base, w in A:
    if base <= va < base + 4 * len(w):
        i = (va - base) // 4
        pat = [sh16(x) for x in w[i:i + n]]
assert pat
for base, w in B:
    sh = [sh16(x) for x in w]
    for i in range(len(sh) - n):
        if sh[i] == pat[0] and sh[i:i + n] == pat:
            print(f'{va:08X} -> {base + 4 * i:08X}')
