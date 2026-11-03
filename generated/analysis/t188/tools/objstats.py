#!/usr/bin/env python3
"""T188: per-function static x64 statistics of an object file (llvm-objdump, Intel syntax).

  objstats.py <a.obj> [<b.obj>] [--src <lift.cpp>] [--top N] [--fn func_X]

Counts per func_*: instructions, calls, branches, memory operands split into
  ctx   [reg + disp] with no index, disp < 0x440, reg not rsp/rbp  (guest-state fields;
        heuristic: the ppu_context layout puts gpr/fpr/vr/cr/lr/ctr/xer below 0x440)
  stk   rsp/rbp relative (host spills and the /GS slot)
  other everything else (guest memory, globals, TLS)
With two objects: the totals over the functions both define, and the ratio.
--src gives guest instruction counts (one lifted statement line per guest instruction)."""
import re, subprocess, sys
from collections import Counter
from pathlib import Path

OBJDUMP = str(Path(__file__).resolve().parents[4] / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/llvm-objdump.exe')
FN = re.compile(r'^[0-9a-f]+ <(\??func_[0-9A-F]{8})[^>]*>:')
MEM = re.compile(r'\[([^\]]*)\]')


def stats(obj):
    out = subprocess.run([OBJDUMP, '-d', '--no-show-raw-insn', '-M', 'intel', '--no-leading-addr', obj],
                         capture_output=True, text=True, errors='replace').stdout
    res, cur = {}, None
    for line in out.splitlines():
        m = re.match(r'^<(\??func_[0-9A-F]{8})[^>]*>:', line) or FN.match(line)
        if m:
            cur = res.setdefault(m.group(1).lstrip('?'), Counter())
            continue
        if cur is None:
            continue
        s = line.strip()
        if not s or s.endswith(':') or s.startswith(('<', ';')):
            if s.startswith('<') and s.endswith('>:'):
                cur = None
            continue
        parts = s.split(None, 1)
        op, args = parts[0], parts[1] if len(parts) > 1 else ''
        if op in ('int3', 'nop') or op.startswith('nop'):
            continue
        cur['insn'] += 1
        if op == 'call':
            cur['call'] += 1
        elif op.startswith('j'):
            cur['branch'] += 1
        if op == 'lea':
            continue
        for mm in MEM.finditer(args):
            e = mm.group(1).replace(' ', '')
            if 'rsp' in e or 'rbp' in e:
                cur['stk'] += 1
            elif 'rip' in e or ':' in e or '*' in e:
                cur['other'] += 1
            else:
                t = e.split('+')
                regs = [x for x in t if re.fullmatch(r'r\w+|e\w+', x)]
                disp = [x for x in t if x.startswith('0x')]
                d = int(disp[0], 16) if disp else 0
                if len(regs) == 1 and d < 0x440 and '-' not in e:
                    cur['ctx'] += 1
                else:
                    cur['other'] += 1
    return res


def guest_counts(src):
    d = open(src, encoding='latin-1').read()
    out = {}
    for m in re.finditer(r'^void (func_[0-9A-F]{8})\(ppu_context\* ctx\) \{(.*?)^\}$', d, re.M | re.S):
        n = 0
        for l in m.group(2).split('\n'):
            t = l.strip()
            if t and not re.fullmatch(r'loc_[0-9A-F]+:.*', t) or re.match(r'loc_[0-9A-F]+:', t) and False:
                if not t.startswith(('uint64_t _cs_', '{ g_trampoline_fn')):
                    n += 1
        out[m.group(1)] = n
    return out


def main(a):
    top = int(a[a.index('--top') + 1]) if '--top' in a else 0
    fn = a[a.index('--fn') + 1] if '--fn' in a else None
    src = a[a.index('--src') + 1] if '--src' in a else None
    objs = [x for i, x in enumerate(a) if x.endswith('.obj') and (i == 0 or a[i - 1] not in ('--src',))]
    S = [stats(o) for o in objs]
    keys = ('insn', 'ctx', 'stk', 'other', 'call', 'branch')
    common = set(S[0])
    for s in S[1:]:
        common &= set(s)
    g = guest_counts(src) if src else {}
    tot = [Counter() for _ in S]
    for f in common:
        for i, s in enumerate(S):
            tot[i].update(s[f])
    gi = sum(g.get(f, 0) for f in common)
    print(f'functions in common: {len(common)}' + (f', guest insns {gi}' if g else ''))
    for o, t in zip(objs, tot):
        extra = f'  insn/guest={t["insn"] / gi:.2f} ctx/guest={t["ctx"] / gi:.2f}' if gi else ''
        print(f'{Path(o).name:20s} ' + ' '.join(f'{k}={t[k]}' for k in keys) + extra)
    if len(S) == 2:
        print('ratio b/a            ' + ' '.join(f'{k}={tot[1][k] / max(1, tot[0][k]):.3f}' for k in keys))
        if top:
            rows = sorted(common, key=lambda f: -S[0][f]['insn'])[:top]
            for f in rows:
                print(f'  {f} guest={g.get(f, "?")} ' + ' '.join(f'{k}={S[0][f][k]}->{S[1][f][k]}' for k in ('insn', 'ctx', 'stk', 'call')))
    if fn:
        for o, s in zip(objs, S):
            print(o, fn, dict(s.get(fn, {})))


if __name__ == '__main__':
    main(sys.argv[1:])
