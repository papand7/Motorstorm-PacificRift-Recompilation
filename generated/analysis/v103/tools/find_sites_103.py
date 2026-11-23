"""Find the 1.03 addresses of 1.02 PPU sites: take a window of instruction words around each 1.02
address and search for it in the 1.03 ELF's executable segments (unique match required).
usage: py -3 find_sites_103.py <hex addr> ...   (prints 1.02 addr -> 1.03 addr, window, match count)"""
import pathlib, struct, sys
R = pathlib.Path(__file__).resolve().parents[4]
E102 = R / 'generated/decrypted/EBOOT.elf'
E103 = R / 'generated/decrypted/v103/EBOOT_103.elf'

def segs(p):
    b = p.read_bytes()
    phoff, = struct.unpack_from('>Q', b, 0x20); phn, = struct.unpack_from('>H', b, 0x38)
    out = []
    for i in range(phn):
        t, fl, off, va, pa, fs, ms, al = struct.unpack_from('>IIQQQQQQ', b, phoff + 56 * i)
        if t == 1 and fl & 1: out.append((va, b[off:off + fs]))
    return out

def read(sg, va, n):
    for base, d in sg:
        if base <= va and va + n <= base + len(d): return d[va - base: va - base + n]

def find(sg, pat):
    hits = []
    for base, d in sg:
        i = d.find(pat)
        while i >= 0:
            if i % 4 == 0: hits.append(base + i)
            i = d.find(pat, i + 1)
    return hits

a, b = segs(E102), segs(E103)
for arg in sys.argv[1:]:
    va = int(arg, 16)
    for w in (8, 16, 32, 64):   # words before and after
        pat = read(a, va - 4 * w, 8 * w + 4)
        if pat is None: break
        h = find(b, pat)
        if len(h) == 1:
            print(f'{va:08X} -> {h[0] + 4 * w:08X}  (window +-{w} words, unique)'); break
        if not h:
            # shrink: try only after / only before
            for nm, s, n in (('after', va, 4 * w + 4), ('before', va - 4 * w, 4 * w + 4)):
                hh = find(b, read(a, s, n))
                if len(hh) == 1:
                    print(f'{va:08X} -> {hh[0] + (va - s):08X}  ({nm} {w} words, unique)'); break
            else:
                print(f'{va:08X} -> no match at +-{w} words'); 
            break
    else:
        print(f'{va:08X} -> ambiguous')
