#!/usr/bin/env python3
"""T152: cut lifted functions out of the staging lift into a standalone TU.

  python extract_fn.py <out.cpp> func_XXXXXXXX [func_...]

Output: the TU prelude of the file that defines the first function (helpers, macros,
externs), then each requested body. Every other func_* stays an extern declared by
ppu_recomp.h, so the TU compiles with -I <dir holding a ppu_recomp.h>. Nothing is
written into generated/ppu-hooked-staging.
"""
import re
import sys
from pathlib import Path

STAGING = Path(__file__).resolve().parents[3] / 'ppu-hooked-staging'
FN = re.compile(rb'^void (func_[0-9A-F]{8})\(ppu_context\* ctx\) \{', re.M)


def locate(names):
    """name -> (file, start, end) by scanning each TU once."""
    want, found = set(names), {}
    for f in sorted(STAGING.glob('ppu_recomp_*.cpp')):
        data = f.read_bytes()
        hits = list(FN.finditer(data))
        for i, m in enumerate(hits):
            n = m.group(1).decode()
            if n in want:
                end = hits[i + 1].start() if i + 1 < len(hits) else len(data)
                found[n] = (f, data[m.start():end])
        if want <= found.keys():
            break
    return found


def prelude(f):
    data = f.read_bytes()
    m = FN.search(data)
    return data[:m.start()]


def main():
    out, names = Path(sys.argv[1]), sys.argv[2:]
    found = locate(names)
    miss = [n for n in names if n not in found]
    if miss:
        sys.exit(f'not found: {miss}')
    parts = [prelude(found[names[0]][0])]
    for n in names:
        parts.append(found[n][1])
    out.write_bytes(b''.join(parts))
    for n in names:
        print(f'{n}: {found[n][0].name}, {len(found[n][1])} bytes')


if __name__ == '__main__':
    main()
