#!/usr/bin/env python3
"""T152: per-function instruction statistics of clang-cl /FA output.

  python asm_stats.py <fn.asm> [<fn.asm> ...]

For every func_XXXXXXXX body: instructions, calls (by target), memory loads/stores (any
[...] operand; stack-relative ones separately), bswaps, and lock-prefixed/fence instructions.
"""
import re
import sys
from collections import Counter

LABEL = re.compile(r'^"?\??(func_[0-9A-F]{8})\S*:')


def stats(path):
    out, cur = {}, None
    for line in open(path, encoding='utf-8', errors='replace'):
        m = LABEL.match(line)
        if m:
            cur = out.setdefault(m.group(1), Counter())
            continue
        if cur is None or not line.startswith('\t') or line.lstrip().startswith(('#', '.')):
            if line.startswith('\t.seh_endproc') or line.startswith('\t.cv_'):
                pass
            continue
        ins = line.strip().split(None, 1)
        if not ins or ins[0].endswith(':'):
            continue
        op, args = ins[0], ins[1] if len(ins) > 1 else ''
        cur['insn'] += 1
        if op == 'call':
            cur['call'] += 1
            cur['call:' + args.split()[-1].strip('"')] += 1
        if op.startswith('j'):
            cur['branch'] += 1
        if '[' in args:
            mem = args[args.index('['):args.index(']') + 1]
            first = args.split(',')[0]
            kind = 'store' if '[' in first and op.startswith(('mov', 'add', 'or', 'and', 'sub', 'xor', 'inc', 'dec')) else 'load'
            if op in ('lea',):
                continue
            stack = 'rsp' in mem or 'rbp' in mem
            cur[('stk_' if stack else '') + kind] += 1
        if op == 'bswap' or op.startswith('movbe'):
            cur['bswap'] += 1
        if op in ('mfence', 'lock') or args.startswith('lock') or op.startswith('xchg'):
            cur['fence'] += 1
    return out


def main():
    for p in sys.argv[1:]:
        print(f'== {p}')
        for fn, c in sorted(stats(p).items()):
            calls = ', '.join(f'{k[5:]}={v}' for k, v in c.most_common() if k.startswith('call:'))
            print(f'  {fn}: insn={c["insn"]} load={c["load"]} store={c["store"]} stk_load={c["stk_load"]} '
                  f'stk_store={c["stk_store"]} branch={c["branch"]} bswap={c["bswap"]} call={c["call"]} [{calls}]')


if __name__ == '__main__':
    main()
