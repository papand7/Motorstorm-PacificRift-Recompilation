#!/usr/bin/env python3
"""T84B: annotated disassembly of a retail-ELF range (offline, read-only).
Annotates lwz rD,d(r2) with the TOC slot's value (and the string there, if printable) for the
given TOC base, and bl targets.  py -3 ppcdis84.py <start hex> <end hex> [toc hex, default 10AFBE4]"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import elf


def ann_toc(toc, d):
    slot = toc + d
    v = elf.u32(slot)
    if v is None:
        return ''
    s = elf.cstr(v, 48) if elf.rd(v, 1) else ''
    s = s if s and all(32 <= ord(c) < 127 for c in s) and len(s) >= 3 else ''
    f = elf.f32(v) if elf.rd(v, 4) else None
    extra = f' "{s}"' if s else (f' f={f:.6g}' if f is not None and 1e-6 < abs(f) < 1e7 else '')
    return f'  ; [toc{d:+#x}]=0x{v:08X}{extra}'


def main(a0, a1, toc):
    for a, m, ops in elf.disasm(a0, a1):
        note = ''
        mm = re.match(r'r\d+, (-?0x[0-9a-f]+|-?\d+)\(r2\)$', ops)
        if m in ('lwz', 'lfs', 'lfd') and mm:
            note = ann_toc(toc, int(mm.group(1), 0))
        print(f'{a:08x}  {m:8s} {ops}{note}')


if __name__ == '__main__':
    a = sys.argv[1:]
    main(int(a[0], 16), int(a[1], 16), int(a[2], 16) if len(a) > 2 else 0x010AFBE4)
