"""gen_native.py: flush only the registers written since the last flush before a channel call.

Invariant: a register that is not dirty holds the same value in R[] and ctx->gpr (the runtime does
not write ctx->gpr inside rdch/wrch/rchcnt; their results come back as return values). Dirty sets
are joined over every edge into a label (a fixpoint over gotos and fallthrough)."""
import re

R_LAB = re.compile(r'^(loc_[0-9A-Fa-f]{8}|\w+_fast\d+|sc\d+_loc_[0-9A-Fa-f]{8}):')
R_GOTO = re.compile(r'goto (\w+);')
R_DEF = re.compile(r'R\[(\d+)\] = ')
CALL = '({ STORE_ALL(); spu_'


def _walk(lines, din, emit):
    dirty, out = set(), []
    for t in lines:
        s = t.strip()
        m = R_LAB.match(s)
        if m:
            dirty = dirty | din.get(m.group(1), set())
            out.append(t)
            continue
        if CALL in s:
            stores = ' '.join(f'ctx->gpr[{n}] = R[{n}];' for n in sorted(dirty))
            t = t.replace('STORE_ALL(); spu_', (stores + ' ' if stores else '') + 'spu_', 1)
            dirty = set()
        for g in R_GOTO.findall(s):
            din.setdefault(g, set())
            if not dirty <= din[g]:
                din[g] |= dirty
                emit[0] = True
        dirty |= set(int(x) for x in R_DEF.findall(s))
        if (s.startswith('{') or s.startswith('goto ')) and ('goto ' in s or 'return 1' in s):
            dirty = set()   # unconditional: nothing falls through
        out.append(t)
    return out


def dirty_flush(lines):
    if not any(CALL in l for l in lines):
        return lines
    din = {}
    while True:
        changed = [False]
        out = _walk(lines, din, changed)
        if not changed[0]:
            return out
