#!/usr/bin/env python3
"""T82: every computed `bi $rA` (rA != r0) in a WWS job module, the words that follow it read both as
absolute and as table-relative targets, and whether each target is a registered lifted entry.

  py -3 -I switch_sites.py <module .bin> <lifted spu_recomp.c> [--base 0x4000]

Registered entries = the { 0x....u, fn, "name" } rows of the lifted TU's registration table."""
import re, struct, sys

BASE = 0x4000


def main(binp, cp, base=BASE):
    raw = open(binp, 'rb').read()
    src = open(cp, errors='replace').read()
    reg = {int(m.group(1), 16) for m in re.finditer(r'\{ 0x([0-9A-F]{8})u, \w+, "', src)}
    ilas = {}
    for off in range(0x30, len(raw) - 4, 4):
        w = struct.unpack_from('>I', raw, off)[0]
        if (w >> 25) & 0x7F == 0x21:
            ilas.setdefault((w >> 7) & 0x3FFFF, []).append(base + off)
    print(f'module {binp} size 0x{len(raw):X} registered entries {len(reg)}')
    tot_abs = tot_unreg = 0
    for off in range(0x30, len(raw) - 4, 4):
        w = struct.unpack_from('>I', raw, off)[0]
        if (w >> 21) & 0x7FF != 0x1A8:            # bi family (bi/bie/bid share opcode 0x1A8)
            continue
        ra = (w >> 7) & 0x7F
        ie = (w >> 18) & 3
        if ra == 0:
            continue
        prev = [struct.unpack_from('>I', raw, off - 4 * k)[0] for k in (1, 2, 3)]
        # an `ila $ra, X` right before (bie/bid fence idiom): target X
        ila_t = None
        for k, p in enumerate(prev, 1):
            if (p >> 25) & 0x7F == 0x21 and (p & 0x7F) == ra:
                ila_t = (p >> 7) & 0x3FFFF
                break
        if ila_t is not None:
            continue                               # constant target; reported separately
        tbl = off + 4
        ents_abs, ents_rel = [], []
        i = 0
        while tbl + 4 * i + 4 <= len(raw) and i < 64:
            e = struct.unpack_from('>I', raw, tbl + 4 * i)[0]
            if base + 0x30 <= e < base + len(raw) and e % 4 == 0:
                ents_abs.append(e)
            else:
                break
            i += 1
        named = (base + tbl) in ilas or tbl in ilas
        unreg = [e for e in ents_abs if e not in reg]
        tot_abs += len(ents_abs)
        tot_unreg += len(unreg)
        print(f'bi $r{ra} at LS 0x{base + off:05X} (ie={ie}) table@0x{base + tbl:05X} ila-named={named} '
              f'abs entries {len(ents_abs)} unregistered {len(unreg)}: '
              + ' '.join(f'{e:05X}{"" if e in reg else "*"}' for e in ents_abs))
    print(f'TOTAL absolute table entries {tot_abs}, not registered (*) {tot_unreg}')
    # constant-target bi (ila; bi) not registered
    bad = []
    for off in range(0x30, len(raw) - 4, 4):
        w = struct.unpack_from('>I', raw, off)[0]
        if (w >> 21) & 0x7FF != 0x1A8 or ((w >> 7) & 0x7F) == 0:
            continue
        ra = (w >> 7) & 0x7F
        for k in (1, 2, 3):
            p = struct.unpack_from('>I', raw, off - 4 * k)[0]
            if (p >> 25) & 0x7F == 0x21 and (p & 0x7F) == ra:
                t = (p >> 7) & 0x3FFFF
                if t not in reg:
                    bad.append((base + off, t))
                break
    print(f'constant-target (ila;bi) sites with an unregistered target: {len(bad)} '
          + ' '.join(f'{a:05X}->{t:05X}' for a, t in bad[:20]))


if __name__ == '__main__':
    a = sys.argv[1:]
    b = BASE
    if '--base' in a:
        i = a.index('--base'); b = int(a[i + 1], 16); del a[i:i + 2]
    main(a[0], a[1], b)
