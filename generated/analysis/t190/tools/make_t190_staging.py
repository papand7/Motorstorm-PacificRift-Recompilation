#!/usr/bin/env python3
"""T190: generated/ppu-t190-staging = generated/ppu-t173-staging (the lift every T18x exe used), NOT re-lifted.
Lifted sources: hard links (ppu_hle_nids.cpp a copy; the build rewrites it). ppu_recomp.h = the staging
header with ONE block replaced (method of t152/tools/make_t152_lift.py): the old vm_inl_ok gate, verified
verbatim, by the block between the T152 page-gate markers of the T189 lifter's header template
(ps3recomp-t190 = a26240c5). --check: verify only."""
import filecmp, hashlib, os, shutil, sys
from pathlib import Path
M = Path(__file__).resolve().parents[4]
SRC, DST = M / 'generated/ppu-t173-staging', M / 'generated/ppu-t190-staging'
LIFTER = M / 'ps3recomp-t190/tools/ppu_lifter.py'
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
B0, B1 = '/* T152 page gates: begin */', '/* T152 page gates: end */'
def block():
    t = LIFTER.read_bytes().decode('utf-8').replace('\r\n', '\n')
    a, b = t.index(B0), t.index(B1) + len(B1)
    blk = t[a:b] + '\n'
    assert chr(92) not in blk, 'escape in block'
    return blk
def header():
    h = (SRC / 'ppu_recomp.h').read_bytes().decode('latin-1')
    crlf = '\r\n' in h
    h = h.replace('\r\n', '\n')
    anchor = 'extern uint32_t ppu_hle_inject_base;\n'
    i = h.index(anchor) + len(anchor)
    if h.count(OLD) != 1 or not h[i:].startswith(OLD):
        sys.exit('staging header: old gate block not where expected; refusing')
    h = h[:i] + block() + h[i + len(OLD):]
    return h.replace('\n', '\r\n') if crlf else h
def main():
    hdr = header()
    print(f'header {len(hdr)} B (staging {(SRC / "ppu_recomp.h").stat().st_size} B), sha256 {hashlib.sha256(hdr.encode("latin-1")).hexdigest()}')
    if '--check' in sys.argv: return
    DST.mkdir(exist_ok=True)
    n = 0
    for f in sorted(SRC.iterdir()):
        if f.suffix not in ('.cpp', '.c') or not f.is_file(): continue
        d = DST / f.name
        if f.name == 'ppu_hle_nids.cpp':
            shutil.copy2(f, d)
        elif not d.exists():
            os.link(f, d)
        assert filecmp.cmp(f, d, shallow=False), f
        n += 1
    (DST / 'ppu_recomp.h').write_bytes(hdr.encode('latin-1'))
    print(f'{DST}: {n} sources (identical to staging), ppu_recomp.h patched')
if __name__ == '__main__': main()
