#!/usr/bin/env python3
"""T152: a private copy of the staging lift whose ppu_recomp.h carries the T152 page gates.

  python make_t152_lift.py [--check]

Copies generated/ppu-hooked-staging/*.cpp unchanged to generated/ppu-t152-staging/ and writes
ppu_recomp.h = the staging header with ONE block replaced: the old vm_inl_ok gate (verified
verbatim) by the block between "/* T152 page gates: begin */" and "... end */" in the T152
lifter's header template (ps3recomp-t152-ppu-performance/tools/ppu_lifter.py). Nothing is
re-lifted; the staging directory is only read. --check: only verify and print the diff size.
"""
import filecmp
import shutil
import sys
from pathlib import Path

M = Path(__file__).resolve().parents[4]
SRC = M / 'generated/ppu-hooked-staging'
DST = M / 'generated/ppu-t152-staging'
LIFTER = M / 'ps3recomp-t152-ppu-performance/tools/ppu_lifter.py'

OLD = '''#ifdef __cplusplus
}
#endif
static inline int vm_inl_ok(uint32_t ea, uint32_t n)
{
    return __builtin_expect(vm_inline_ok, 1) && ea >= 0x10000u && ea < 0xE0000000u &&
           ea != ppu_hle_inject_base + 0x2008u &&
           (ppu_vm_size == 0 || (uint64_t)ea + n <= ppu_vm_size);
}
'''


def new_block():
    t = LIFTER.read_bytes().decode('utf-8').replace('\r\n', '\n')
    a = t.index('/* T152 page gates: begin */')
    b = t.index('/* T152 page gates: end */') + len('/* T152 page gates: end */')
    return t[a:b] + '\n'


def patched_header():
    h = (SRC / 'ppu_recomp.h').read_bytes().decode('latin-1')
    crlf = '\r\n' in h
    h = h.replace('\r\n', '\n')
    anchor = 'extern uint32_t ppu_hle_inject_base;\n'
    i = h.index(anchor) + len(anchor)
    if h.count(OLD) != 1 or not h[i:].startswith(OLD):
        sys.exit('staging header: the old gate block is not where expected; refusing to patch')
    h = h[:i] + new_block() + h[i + len(OLD):]
    return h.replace('\n', '\r\n') if crlf else h


def main():
    hdr = patched_header()
    if '--check' in sys.argv:
        print(f'patched header: {len(hdr)} bytes (staging {(SRC / "ppu_recomp.h").stat().st_size})')
        return
    DST.mkdir(exist_ok=True)
    n = 0
    for f in sorted(SRC.iterdir()):
        if f.suffix in ('.cpp', '.c') and f.is_file():
            d = DST / f.name
            if not d.exists() or not filecmp.cmp(f, d, shallow=False):
                shutil.copy2(f, d)
            n += 1
    (DST / 'ppu_recomp.h').write_bytes(hdr.encode('latin-1'))
    print(f'{DST}: {n} sources copied unchanged, ppu_recomp.h patched')


if __name__ == '__main__':
    main()
