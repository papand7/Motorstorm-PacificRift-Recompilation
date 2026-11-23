"""Give the Vulkan build's lift (generated/ppu-t173-staging) the T152 page gates and inline stores.

  py -3 ppu_header_gates.py [--check]

Replaces ONE block of ppu_recomp.h: the old vm_inl_ok gate (verified verbatim, right after
`extern uint32_t ppu_hle_inject_base;`) by the block between "/* T152 page gates: begin */" and
"... end */" of this tree's lifter (ps3recomp-vkgame/tools/ppu_lifter.py), the same swap as
generated/analysis/t152/tools/make_t152_lift.py. The header is a hard link shared with
generated/ppu-hooked-staging, so the link is broken first (copy, then replace): the hooked staging
keeps its header. Nothing is re-lifted. Idempotent. --check: verify only.
"""
import os
import shutil
import sys
from pathlib import Path

M = Path(__file__).resolve().parents[4]
H = M / 'generated/ppu-t173-staging/ppu_recomp.h'
LIFTER = M / 'ps3recomp-vkgame/tools/ppu_lifter.py'
BEGIN, END = '/* T152 page gates: begin */', '/* T152 page gates: end */'
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
    a = t.index(BEGIN)
    b = t.index(END) + len(END)
    return t[a:b] + '\n'


def main():
    h = H.read_bytes().decode('latin-1')
    if BEGIN in h:
        print('already patched:', H)
        return 0
    crlf = '\r\n' in h
    h = h.replace('\r\n', '\n')
    anchor = 'extern uint32_t ppu_hle_inject_base;\n'
    i = h.index(anchor) + len(anchor)
    if h.count(OLD) != 1 or not h[i:].startswith(OLD):
        sys.exit('ppu_recomp.h: the old gate block is not where expected; refusing to patch')
    blk = new_block()
    print('block: %d lines replace %d' % (blk.count('\n'), OLD.count('\n')))
    if '--check' in sys.argv:
        return 0
    h = h[:i] + blk + h[i + len(OLD):]
    if crlf:
        h = h.replace('\n', '\r\n')
    tmp = H.with_suffix('.h.tmp')
    shutil.copyfile(H, tmp)          # a separate file: the hard link to the hooked staging is broken
    tmp.write_bytes(h.encode('latin-1'))
    os.replace(tmp, H)
    print('patched:', H, 'links now', os.stat(H).st_nlink)
    return 0


if __name__ == '__main__':
    sys.exit(main())
