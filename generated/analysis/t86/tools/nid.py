"""T86: resolve a PPU call target to an import NID (follow b-stubs / first bl into an import stub,
then the import stub's lwz slot -> sceLibStub fstub table -> fnid table).  python nid.py <hex> ..."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 't84' / 'tools'))
import elf

def btarget(a):
    w = elf.u32(a) or 0
    if (w >> 26) != 18: return None
    off = w & 0x3FFFFFC
    if off & 0x2000000: off -= 0x4000000
    return a + off, bool(w & 1)

def import_slot(a):
    """Import stub: li/lis r12 ...; lwz r12,lo(r12) -> slot EA."""
    w0, w1, w2 = (elf.u32(a + i * 4) or 0 for i in range(3))
    if w0 >> 16 == 0x3980 and w1 >> 16 == 0x658C and w2 >> 16 == 0x818C:
        lo = w2 & 0xFFFF
        lo = lo - 0x10000 if lo & 0x8000 else lo
        return ((w1 & 0xFFFF) << 16) + (w0 & 0xFFFF) + lo
    return None

STUBS = []
def load_stubs():
    # sceLibStub: 0x2C bytes, byte0 = 0x2C, +0x6 num_func(u16), +0x10 libname, +0x14 fnid, +0x18 fstub
    for a in elf.find_bytes(b'\x2c\x00'):
        if a % 4: continue
        n = (elf.u32(a + 4) or 0) & 0xFFFF
        lib, fnid, fstub = (elf.u32(a + o) for o in (0x10, 0x14, 0x18))
        if not (0 < n < 2000 and lib and fnid and fstub): continue
        name = elf.cstr(lib, 40)
        if name and name.isprintable(): STUBS.append((fstub, n, fnid, name))

def resolve(a, depth=0):
    s = import_slot(a)
    if s is not None:
        for fstub, n, fnid, name in STUBS:
            if fstub <= s < fstub + 4 * n:
                return f'{name} NID 0x{elf.u32(fnid + (s - fstub)):08X} (stub {a:08x})'
        return f'import slot {s:08x} (unresolved)'
    if depth > 3: return None
    for x in range(a, a + 0x200, 4):
        t = btarget(x)
        if t and (t[1] or x == a + 12 or x - a < 16):
            r = resolve(t[0], depth + 1)
            if r: return f'{a:08x} -> ' + r
        if (elf.u32(x) or 0) == 0x4E800020: break
    return None

load_stubs()
for h in sys.argv[1:]:
    print(h, resolve(int(h, 16)))
