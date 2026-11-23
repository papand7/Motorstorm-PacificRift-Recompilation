"""spunat3 generator pass: speculative x86 single precision for a straight-line region (spu_nx.h).

nx_region(lines) rewrites local-form statements (`R_t = spu_op(R_a, ...);`):
  - spu_fa/fs/fm/fma/fms/fnms -> nx_<op>(&_nxb, ...) (bad-lane mask, -0 -> +0), or nx_<op>z (no -0 fix)
    when the result is redefined later in the region and every read before that is an operand that
    treats -0 and +0 alike (the arithmetic itself, frsqest, cflts, fi's first operand, float compares);
  - spu_frest/frsqest/cflts/csflt -> the nx_ forms (exact, no mask).
The caller declares `__m128i _nxb`, runs the region under NX_ENTER, tests NX_ANY(_nxb) before any of
the region's results become visible and recomputes the region with the original statements if set."""
import re

FP = {'fa', 'fs', 'fm', 'fma', 'fms', 'fnms'}
RE_DEF = re.compile(r'^\s*R_(\d+) = spu_([a-z0-9_]+)\((.*)\);\s*$')


def _args(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == ',' and depth == 0:
            out.append(cur.strip()); cur = ''
            continue
        depth += ch == '('
        depth -= ch == ')'
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _safe_use(line, reg):
    """every occurrence of R_reg in line is an operand that reads -0 and +0 alike"""
    tok = f'R_{reg}'
    if not re.search(rf'\b{tok}\b', line):
        return True
    m = RE_DEF.match(line)
    if not m:
        return False
    op, args = m.group(2), _args(m.group(3))
    for i, a in enumerate(args):
        if not re.search(rf'\b{tok}\b', a):
            continue
        if a != tok:
            return False
        if op in FP or op in ('frsqest', 'fcgt', 'fcmgt', 'fceq', 'fcmeq'):
            continue
        if op == 'cflts' and i == 0:
            continue
        if op == 'fi' and i == 0:
            continue
        return False
    return True


def nx_region(lines, fix_all=False):
    out = []
    for i, l in enumerate(lines):
        m = RE_DEF.match(l)
        if m and m.group(2) in FP:
            t = int(m.group(1))
            nofix = False
            if not fix_all:
                for j in range(i + 1, len(lines)):
                    if not _safe_use(lines[j], t):
                        break
                    mj = RE_DEF.match(lines[j])
                    if mj and int(mj.group(1)) == t:
                        nofix = True   # redefined; the -0 never reached a sign-sensitive reader
                        break
            l = re.sub(rf'\bspu_{m.group(2)}\(', f'nx_{m.group(2)}{"z" if nofix else ""}(&_nxb, ', l, count=1)
        else:
            l = re.sub(r'\bspu_(frest|frsqest|cflts|csflt)\(', r'nx_\1(', l)
        out.append(l)
    return out


RE_ST = re.compile(r'^(\s*)spu_ls_write128_ls\(ctx, ls, (?:0|_spu_lsd), (.*), (R_\d+)\);\s*$')


def _is_load(l):
    return 'spu_ls_read128' in l


def _is_plain(l):
    return bool(RE_DEF.match(l)) or l.strip().startswith('_st')


def sink_stores(lines):
    """Move the LS stores of a straight-line block after its last statement when no LS load follows
    them in the block: the address and value are captured where the store was (`_sta[k] = ...;
    _stv[k] = ...;`, pure statements a speculative region may contain) and the stores are made, in
    their original order, right before the block's terminating branch/label/exit. Returns
    (lines, number of capture slots needed)."""
    out, pend, nmax = [], [], 0
    blk_start = 0

    def end_block():
        out.extend(pend)
        pend.clear()

    i = 0
    while i < len(lines):
        l = lines[i]
        m = RE_ST.match(l)
        if m:
            # any load later in this block?
            j, later_load = i + 1, False
            while j < len(lines) and (_is_plain(lines[j]) or RE_ST.match(lines[j])):
                if _is_load(lines[j]):
                    later_load = True
                    break
                j += 1
            if not later_load:
                k = len(pend)
                nmax = max(nmax, k + 1)
                ind = m.group(1)
                out.append(f'{ind}_sta[{k}] = {m.group(2)};')
                out.append(f'{ind}_stv[{k}] = {m.group(3)};')
                pend.append(f'{ind}spu_ls_write128_ls(ctx, ls, 0, _sta[{k}], _stv[{k}]);')
                i += 1
                continue
            end_block()
            out.append(l)
        elif _is_plain(l):
            out.append(l)
        else:
            end_block()
            out.append(l)
        i += 1
    end_block()
    return out, nmax
