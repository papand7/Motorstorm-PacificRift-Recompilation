"""T84B: read-only helpers over the private retail ELF (generated/decrypted/EBOOT.elf).
Guest pointers are 32-bit big-endian; function descriptors are (entry, TOC) pairs of 32-bit words.
Import from other t84 tools; prints nothing itself."""
import re, struct
from pathlib import Path

ELF = Path(__file__).resolve().parents[3] / 'decrypted' / 'EBOOT.elf'
D = ELF.read_bytes()
_phoff = struct.unpack('>Q', D[0x20:0x28])[0]
_phentsz, _phnum = struct.unpack('>HH', D[0x36:0x3a])
SEGS = []   # (va, file offset, file size, flags)
for _i in range(_phnum):
    _t, _fl, _off, _va, _pa, _fsz, _msz, _al = struct.unpack('>IIQQQQQQ', D[_phoff + _i * _phentsz:_phoff + _i * _phentsz + 56])
    if _t == 1 and _fsz:
        SEGS.append((_va, _off, _fsz, _fl))
TEXT = [s for s in SEGS if s[3] & 1]


def rd(a, n):
    for va, off, fsz, _ in SEGS:
        if va <= a and a + n <= va + fsz:
            return D[off + a - va:off + a - va + n]
    return None


def u32(a):
    b = rd(a, 4)
    return None if b is None else struct.unpack('>I', b)[0]


def f32(a):
    b = rd(a, 4)
    return None if b is None else struct.unpack('>f', b)[0]


def cstr(a, n=96):
    b = rd(a, n) or b''
    return b.split(b'\0')[0].decode('latin1')


def find_bytes(pat):
    """Every VA where the byte string occurs."""
    out = []
    for va, off, fsz, _ in SEGS:
        for m in re.finditer(re.escape(pat), D[off:off + fsz]):
            out.append(va + m.start())
    return out


def find_word(w, aligned=True):
    """Every VA holding the 32-bit word w."""
    return [a for a in find_bytes(struct.pack('>I', w)) if not aligned or a % 4 == 0]


def words(seg):
    va, off, fsz, _ = seg
    return va, struct.unpack(f'>{fsz // 4}I', D[off:off + fsz // 4 * 4])


def branches_to(targets):
    """{target: [(site, 'bl'|'b')]} for relative I-form branches in executable segments."""
    targets = set(targets)
    out = {t: [] for t in targets}
    for seg in TEXT:
        va, ws = words(seg)
        for k, w in enumerate(ws):
            if w >> 26 != 18 or w & 2:
                continue
            li = w & 0x03FFFFFC
            if li & 0x02000000:
                li -= 0x04000000
            t = (va + 4 * k + li) & 0xFFFFFFFF
            if t in targets:
                out[t].append((va + 4 * k, 'bl' if w & 1 else 'b'))
    return out


def disasm(a0, a1):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_64 | capstone.CS_MODE_BIG_ENDIAN)
    return [(i.address, i.mnemonic, i.op_str) for i in md.disasm(rd(a0, a1 - a0), a0)]


def func_start(a, limit=0x4000):
    """Nearest preceding 'stdu r1,-N(r1)' with 'mflr r0' within 3 words: a prologue heuristic."""
    for x in range(a, a - limit, -4):
        if (u32(x) or 0) >> 16 == 0xF821:
            near = [u32(x + d) for d in (-8, -4, 4, 8)]
            if 0x7C0802A6 in near:
                return x - 4 if u32(x - 4) == 0x7C0802A6 else (x - 8 if u32(x - 8) == 0x7C0802A6 else x)
    return None


def rtti(mangled):
    """(typeinfo VA, [vtable address points]) for a class name string like b'N3evo3pvs15PVSComputerImplE'."""
    res = []
    for s in find_bytes(mangled + b'\0'):
        if rd(s - 1, 1) not in (b'\0',) and not rd(s - 1, 1).isalnum():
            pass
        for ref in find_word(s):
            ti = ref - 4           # typeinfo = {vptr, name}
            vts = [x + 4 for x in find_word(ti) if u32(x) is not None and u32(x - 4) == 0 or u32(x - 4) is not None and (u32(x - 4) or 0) >= 0xFFFF0000]
            res.append((ti, sorted(set(vts))))
    return res


def vtable_entries(vt, n=24):
    """[(slot offset, descriptor VA, entry, toc)] reading descriptor pointers until a non-descriptor."""
    out = []
    for i in range(n):
        dsc = u32(vt + 4 * i)
        if not dsc:
            break
        e, t = u32(dsc), u32(dsc + 4)
        if e is None or t is None or not any(va <= e < va + fsz for va, off, fsz, fl in TEXT):
            break
        out.append((4 * i, dsc, e, t))
    return out
