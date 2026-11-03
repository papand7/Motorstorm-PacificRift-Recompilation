#!/usr/bin/env python3
"""T152: static inventory of the staging lift, and candidate leaf functions for offline benchmarks.

  python scan_leaves.py [tu_glob=ppu_recomp_0*.cpp] [--top N]

Per TU and in total: lifted functions, scalar loads/stores by width, raw stores, direct calls,
tail-call trampolines, indirect calls, CR updates. Then the largest LEAF functions (no call,
no trampoline, no indirect call, no syscall/HLE) that contain a loop and stores: those can run
in a harness on synthetic guest memory without the rest of the program.
"""
import re
import sys
from collections import Counter
from pathlib import Path

STAGING = Path(__file__).resolve().parents[3] / 'ppu-hooked-staging'
FN = re.compile(r'^void (func_[0-9A-F]{8})\(ppu_context\* ctx\) \{', re.M)
PATS = {
    'ld8': r'vm_read8\(', 'ld16': r'vm_read16\(', 'ld32': r'vm_read32\(', 'ld64': r'vm_read64\(',
    'st8': r'vm_write8\(', 'st16': r'vm_write16\(', 'st32': r'vm_write32\(', 'st64': r'vm_write64\(',
    'raw_st': r'VM_RAW_ST\(|vm_raw_st16\(', 'call': r'\bfunc_[0-9A-F]{8}\(ctx\); DRAIN_TRAMPOLINE',
    'tramp': r'g_trampoline_fn = \(void', 'icall': r'ps3_indirect_call', 'cr': r'ctx->cr = ',
    'sys': r'lv2_syscall|ps3_hle_call', 'stwcx': r'ppu_stwcx', 'fence': r'PPU_FENCE',
}
RX = {k: re.compile(v) for k, v in PATS.items()}


def main():
    glob = next((a for a in sys.argv[1:] if not a.startswith('--') and not a.isdigit()), 'ppu_recomp_0*.cpp')
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 15
    tot, leaves, nfn = Counter(), [], 0
    for f in sorted(STAGING.glob(glob)):
        txt = f.read_text(encoding='utf-8', errors='replace')
        hits = list(FN.finditer(txt))
        nfn += len(hits)
        for i, m in enumerate(hits):
            body = txt[m.end():hits[i + 1].start() if i + 1 < len(hits) else len(txt)]
            c = Counter({k: len(r.findall(body)) for k, r in RX.items()})
            tot += c
            st = c['st8'] + c['st16'] + c['st32'] + c['st64']
            loop = any(int(t, 16) <= int(m.group(1)[5:], 16) + body.find(f'loc_{t}') * 0 for t in [])  # placeholder
            back = len(re.findall(r'goto loc_', body))
            if not (c['call'] or c['tramp'] or c['icall'] or c['sys'] or c['stwcx']) and st >= 4 and back >= 1:
                leaves.append((len(body), m.group(1), f.name, dict(c), back))
    print(f'functions: {nfn}')
    print('static sites:', ', '.join(f'{k}={v}' for k, v in tot.items()))
    leaves.sort(reverse=True)
    print(f'leaf candidates with stores and branches: {len(leaves)}; largest {top}:')
    for n, name, fn, c, back in leaves[:top]:
        print(f'  {name} {fn} {n} B  gotos={back} ' + ' '.join(f'{k}={v}' for k, v in c.items() if v))


if __name__ == '__main__':
    main()
