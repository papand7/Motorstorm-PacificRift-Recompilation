"""gen_native.py --scalar: a lane-0 scalar fast path for the simple loops of a native body.

A loop here is a label loc_L, a body of straight-line statements with forward branches to labels
inside the body, and ONE back edge to loc_L as its last statement. Its fast path runs every
iteration but the last as 32-bit scalar code on word 0 of each register:
  - lanewise word ops (il, ai, a, cgti, selb, shli, ...) become their scalar forms;
  - load-quad / insert (shufb with a cbd/chd/cwd mask) / store-quad on the same address becomes
    one byte / halfword / word store (no quad register is materialised);
  - a whole-quad store of a register the loop never writes stays a quad store;
  - a load whose value feeds scalar code becomes a big-endian word load.
Before each iteration an exit slice (the scalar statements that decide the back edge) says whether
this iteration is the last; the last one then runs as the exact u128 code, so every register the
iteration writes ends exactly as the lifted loop leaves it. Registers the loop carries across
iterations, and those it writes only on some paths, must be lane-uniform (all four words equal) and
come from lanewise ops: their u128 value is then the splat of their scalar shadow (checked at entry
for carried / uniform-needed inputs, tracked with a written flag for path-dependent ones). Anything
the analysis cannot prove -- another op, a loop exit inside the body, a second back edge, a value
needed in all lanes -- leaves the loop as it was. The fast path is taken only when the hoisted
chain check (_ck) holds; step counts match the lifted code (one per chained edge)."""
import re

R_ASSIGN = re.compile(r'^R\[(\d+)\] = (spu_\w+)\((.*)\);$')
R_READ = re.compile(r'^R\[(\d+)\] = spu_ls_read128_ls\(ctx, ls, 0, (.*)\);$')
R_WRITE = re.compile(r'^spu_ls_write128_ls\(ctx, ls, 0, (.*), R\[(\d+)\]\);$')
R_CHAIN = re.compile(r'^(?:if \((?P<cond>[^{]*?)\) )?\{ ctx->pc = (?P<pc>0x[0-9A-Fa-f]+); if \((?P<ok>.*?)\) \{ \+\+nst; '
                     r'goto (?P<lab>loc_[0-9A-Fa-f]{8}); \}.*\}$')
R_GOTO = re.compile(r'^(?:if \((?P<cond>.*)\) )?goto (?P<lab>loc_[0-9A-Fa-f]{8});$')
R_LABEL = re.compile(r'^(loc_[0-9A-Fa-f]{8}):$')
R_REG = re.compile(r'R\[(\d+)\]')
R_COND = re.compile(r'^R\[(\d+)\]\._(u32|u16)\[0\] (==|!=) 0$')

U = 'uint32_t'


def imm(a):
    return f'(({U})(int32_t)({a}))'


# scalar word-0 semantics of the lanewise ops: f(args as C expressions) -> C expression
OPS = {
    'spu_il': lambda a: imm(a[0]),
    'spu_ila': lambda a: f'((({U})({a[0]})) & 0x3FFFFu)',
    'spu_ilhu': lambda a: f'((({U})({a[0]})) << 16)',
    'spu_ilh': lambda a: f'(((({U})({a[0]})) & 0xFFFFu) * 0x10001u)',
    'spu_iohl': lambda a: f'({a[0]} | ((({U})({a[1]})) & 0xFFFFu))',
    'spu_fsmbi': lambda a: (f'(((({a[0]}) >> 15) & 1) ? 0xFF000000u : 0u) | (((({a[0]}) >> 14) & 1) ? 0xFF0000u : 0u) | '
                            f'(((({a[0]}) >> 13) & 1) ? 0xFF00u : 0u) | (((({a[0]}) >> 12) & 1) ? 0xFFu : 0u)'),
    'spu_ai': lambda a: f'({a[0]} + {imm(a[1])})',
    'spu_a': lambda a: f'({a[0]} + {a[1]})',
    'spu_sf': lambda a: f'({a[1]} - {a[0]})',
    'spu_sfi': lambda a: f'({imm(a[1])} - {a[0]})',
    'spu_and': lambda a: f'({a[0]} & {a[1]})',
    'spu_or': lambda a: f'({a[0]} | {a[1]})',
    'spu_xor': lambda a: f'({a[0]} ^ {a[1]})',
    'spu_andc': lambda a: f'({a[0]} & ~{a[1]})',
    'spu_orc': lambda a: f'({a[0]} | ~{a[1]})',
    'spu_nand': lambda a: f'(~({a[0]} & {a[1]}))',
    'spu_nor': lambda a: f'(~({a[0]} | {a[1]}))',
    'spu_eqv': lambda a: f'(~({a[0]} ^ {a[1]}))',
    'spu_andi': lambda a: f'({a[0]} & {imm(a[1])})',
    'spu_ori': lambda a: f'({a[0]} | {imm(a[1])})',
    'spu_xori': lambda a: f'({a[0]} ^ {imm(a[1])})',
    'spu_ceq': lambda a: f'({a[0]} == {a[1]} ? ~0u : 0u)',
    'spu_ceqi': lambda a: f'({a[0]} == {imm(a[1])} ? ~0u : 0u)',
    'spu_cgt': lambda a: f'((int32_t){a[0]} > (int32_t){a[1]} ? ~0u : 0u)',
    'spu_cgti': lambda a: f'((int32_t){a[0]} > (int32_t)({a[1]}) ? ~0u : 0u)',
    'spu_clgt': lambda a: f'({a[0]} > {a[1]} ? ~0u : 0u)',
    'spu_clgti': lambda a: f'({a[0]} > {imm(a[1])} ? ~0u : 0u)',
    'spu_selb': lambda a: f'(({a[0]} & ~{a[2]}) | ({a[1]} & {a[2]}))',
    'spu_shli': lambda a: f'((({a[1]}) & 0x3F) > 31 ? 0u : ({a[0]} << (({a[1]}) & 0x3F)))',
    'spu_rotmi': lambda a: f'(((0 - ({a[1]})) & 0x3F) > 31 ? 0u : ({a[0]} >> ((0 - ({a[1]})) & 0x3F)))',
    'spu_rotmai': lambda a: (f'(((0 - ({a[1]})) & 0x3F) > 31 ? ({U})((int32_t){a[0]} >> 31) : '
                             f'({U})((int32_t){a[0]} >> ((0 - ({a[1]})) & 0x3F)))'),
}
COPY0 = {'spu_shlqbyi', 'spu_rotqbyi', 'spu_shlqbii', 'spu_rotqbii'}   # with a 0 shift: a copy
MASKS = {'spu_cbd': (0xF, 'b'), 'spu_chd': (0xE, 'h'), 'spu_cwd': (0xC, 'w')}


def split_args(s):
    return [x.strip() for x in s.split(',')]


class Refuse(Exception):
    pass


def parse_body(body):
    """statements: dicts with kind, reads, writes, region stack."""
    stmts, regions = [], []
    for line in body:
        t = line.strip()
        m = R_LABEL.match(t)
        if m:
            regions = [r for r in regions if r != m.group(1)]
            stmts.append(dict(kind='label', lab=m.group(1), reg=tuple(regions)))
            continue
        st = dict(reg=tuple(regions), text=t)
        m = R_READ.match(t)
        if m:
            st.update(kind='read', dst=int(m.group(1)), addr=m.group(2), reads=set(map(int, R_REG.findall(m.group(2)))))
            stmts.append(st); continue
        m = R_WRITE.match(t)
        if m:
            st.update(kind='write', addr=m.group(1), src=int(m.group(2)),
                      reads=set(map(int, R_REG.findall(m.group(1)))) | {int(m.group(2))})
            stmts.append(st); continue
        m = R_CHAIN.match(t) or R_GOTO.match(t)
        if m:
            cond = m.group('cond')
            st.update(kind='edge', cond=cond, lab=m.group('lab'), chain=bool(R_CHAIN.match(t)),
                      reads=set(map(int, R_REG.findall(cond or ''))))
            if cond is not None and not R_COND.match(cond):
                raise Refuse('condition ' + cond)
            stmts.append(st)
            regions.append(m.group('lab'))
            continue
        m = R_ASSIGN.match(t)
        if m:
            op, args = m.group(2), split_args(m.group(3))
            st.update(kind='op', dst=int(m.group(1)), op=op, args=args,
                      reads=set(int(x[2:-1]) for x in args if re.fullmatch(r'R\[\d+\]', x)))
            stmts.append(st); continue
        if t == 'spu_arch_fence();':
            st.update(kind='fence', reads=set()); stmts.append(st); continue
        raise Refuse('statement ' + t[:60])
    return stmts


def scalar_loop(body, head, uid):
    """body = lines from `head:` up to and including the back edge. Returns the fast-path lines
    (to place before the head label), or raises Refuse."""
    stmts = parse_body(body)
    back = stmts[-1]
    if back['kind'] != 'edge' or back['lab'] != head or back['cond'] is None:
        raise Refuse('no conditional back edge at the end')
    lab_pos = {s['lab']: i for i, s in enumerate(stmts) if s['kind'] == 'label'}
    for i, s in enumerate(stmts[:-1]):
        if s['kind'] == 'edge':
            if s['lab'] not in lab_pos or s['lab'] == head:
                raise Refuse('edge out of the body or a second back edge')
            if lab_pos[s['lab']] < i:
                raise Refuse('a backward edge inside the body')
    written = {s['dst'] for s in stmts if s['kind'] in ('op', 'read')}
    defs = {}
    for i, s in enumerate(stmts):
        if s['kind'] in ('op', 'read'):
            defs.setdefault(s['dst'], []).append(i)

    def last_def_before(r, i):
        c = [j for j in defs.get(r, []) if j < i]
        return c[-1] if c else None

    # insertion idioms: x = read @A ... m = cXd(p, K) ... y = shufb(v, x, m) ... write @A, y
    idiom, skip = {}, set()
    for i, s in enumerate(stmts):
        if s['kind'] != 'write':
            continue
        j = last_def_before(s['src'], i)
        if j is None or stmts[j]['kind'] != 'op' or stmts[j]['op'] != 'spu_shufb':
            continue
        a = stmts[j]['args']
        if not all(re.fullmatch(r'R\[\d+\]', x) for x in a):
            continue
        v, x, m = (int(z[2:-1]) for z in a)
        jr, jm = last_def_before(x, j), last_def_before(m, j)
        if jr is None or jm is None or stmts[jr]['kind'] != 'read' or stmts[jm]['kind'] != 'op' or \
           stmts[jm]['op'] not in MASKS or stmts[jr]['addr'] != s['addr'] or \
           not re.fullmatch(r'R\[\d+\]', stmts[jm]['args'][0]):
            continue
        if any(stmts[k]['kind'] in ('op', 'read') and stmts[k]['dst'] in stmts[jr]['reads'] for k in range(jr + 1, i)):
            continue    # the address changes between the load and the store
        if any(stmts[k]['kind'] == 'write' for k in range(jr + 1, i)):
            continue    # another store between the load and the store (could alias)
        if not (stmts[jr]['reg'] == stmts[jm]['reg'] == stmts[j]['reg'] == s['reg']) and \
           any(stmts[k]['kind'] in ('label', 'edge') for k in range(min(jr, jm), i)):
            continue    # all four on one path
        idiom[i] = (jr, jm, j)
        skip |= {jr, jm, j}
    # the idiom temporaries may not be used by anything else
    for i, (jr, jm, j) in list(idiom.items()):
        for d in (jr, jm, j):
            r = stmts[d]['dst']
            for k, s in enumerate(stmts):
                if k in (jr, jm, j, i) or s['kind'] == 'label':
                    continue
                if r in s.get('reads', ()) and last_def_before(r, k) == d:
                    raise Refuse(f'r{r} of an insertion is used elsewhere')
    for i, s in enumerate(stmts):
        if s['kind'] == 'op' and i not in skip and s['op'] not in OPS and \
           not (s['op'] in COPY0 and s['args'][1] == '0'):
            raise Refuse('op ' + s['op'])

    # carried (read before a definite write) and path-dependent (last write on a path) registers
    definite, carried = set(), set()
    for s in stmts:
        if s['kind'] == 'label':
            continue
        for r in s.get('reads', ()):
            if r not in definite and r in written:
                carried.add(r)
        if s['kind'] in ('op', 'read') and not s['reg']:
            definite.add(s['dst'])
    # path-dependent: written only on some paths and never unconditionally in the body (an
    # unconditional write later in the iteration is what the exact last iteration leaves behind)
    uncond = {s['dst'] for s in stmts if s['kind'] in ('op', 'read') and not s['reg']}
    maybe = {s['dst'] for s in stmts if s['kind'] in ('op', 'read') and s['reg']} - uncond
    for i, (jr, jm, j) in idiom.items():
        for d in (jr, jm, j):
            if stmts[d]['dst'] in carried | maybe:
                raise Refuse(f'r{stmts[d]["dst"]} of an insertion is live across iterations')

    # need: registers whose u128 value is rebuilt as a splat of the scalar shadow at exit (or before a
    # whole-quad store). Each must be lane-uniform: every def lanewise, every input uniform. Inputs
    # the loop does not write are checked at entry (check); a failed check runs the exact code.
    need = set(carried | maybe)
    for i, s in enumerate(stmts):
        if s['kind'] == 'write' and i not in idiom and s['src'] in written:
            need.add(s['src'])
    check = set(carried)
    seen, work = set(need), list(need)
    while work:
        r = work.pop()
        for d in defs.get(r, []):
            if d in skip:
                raise Refuse(f'r{r} must be uniform but comes from an insertion')
            s = stmts[d]
            if s['kind'] != 'op':
                raise Refuse(f'r{r} must be uniform but comes from a load')
            for q in s['reads']:
                if q in written:
                    if q not in seen:
                        seen.add(q)
                        work.append(q)
                else:
                    check.add(q)

    # exit slice: the statements the back-edge condition depends on (all on the main path)
    creg = int(R_COND.match(back['cond']).group(1))
    slice_idx, want = set(), {creg}
    for i in range(len(stmts) - 2, -1, -1):
        s = stmts[i]
        if s['kind'] in ('op', 'read') and s['dst'] in want:
            if i in skip or s['kind'] == 'read' or s['reg']:
                raise Refuse('the exit depends on a load, an insertion or a path')
            want.discard(s['dst'])
            slice_idx.add(i)
            want |= s['reads']

    def expr(s, local=None):
        args = []
        for a in s['args']:
            m = re.fullmatch(r'R\[(\d+)\]', a)
            if m:
                r = int(m.group(1))
                args.append(local[r] if local and r in local else f's{r}')
            else:
                args.append(a)
        if s['op'] in COPY0 or (s['op'] == 'spu_ori' and s['args'][1] in ('0', '0x0')):
            return args[0]
        return OPS[s['op']](args)

    def cond_c(c, local=None):
        m = R_COND.match(c)
        r = int(m.group(1))
        v = local[r] if local and r in local else f's{r}'
        v = f'(uint16_t){v}' if m.group(2) == 'u16' else v
        return f'{v} {m.group(3)} 0'

    def addr_c(a):
        return R_REG.sub(lambda m: f's{m.group(1)}', a.replace('._u32[0]', ''))

    regs = set()
    for s in stmts:
        regs |= s.get('reads', set())
        if s['kind'] in ('op', 'read'):
            regs.add(s['dst'])
    out = [f'{head}_fast{uid}:']
    conds = [f'R[{q}]._u32[0] == R[{q}]._u32[1] && R[{q}]._u32[0] == R[{q}]._u32[2] && R[{q}]._u32[0] == R[{q}]._u32[3]'
             for q in sorted(check)]
    out.append('if (_ck' + ''.join(f' && {c}' for c in conds) + ') {')
    out.append('    ' + ' '.join(f'{U} s{r} = R[{r}]._u32[0];' for r in sorted(regs)))
    if maybe:
        out.append('    ' + ' '.join(f'int w{r} = 0;' for r in sorted(maybe)))
    for i in sorted(idiom):
        out.append(f'    {U} ad{i} = 0, mk{i} = 0, vv{i} = 0;')
    out.append('    for (;;) {')
    loc, sl = {}, []
    for i in sorted(slice_idx):
        s = stmts[i]
        sl.append(f'const {U} e{i} = {expr(s, loc)};')
        loc[s['dst']] = f'e{i}'
    out.append('        { ' + ' '.join(sl) + f' if (!({cond_c(back["cond"], loc)})) break; }}')
    for i, s in enumerate(stmts[:-1]):
        k = s['kind']
        if k == 'label':
            if s['lab'] != head:
                out.append(f'    sc{uid}_{s["lab"]}: ;')
            continue
        if k == 'fence':
            out.append('        spu_arch_fence();')
            continue
        if k == 'edge':
            inc = '++nst; ' if s['chain'] else ''
            tgt = f'goto sc{uid}_{s["lab"]};'
            out.append(f'        {inc}{tgt}' if s['cond'] is None else f'        if ({cond_c(s["cond"])}) {{ {inc}{tgt} }}')
            continue
        if i in skip:
            for w, (jr, jm, j) in idiom.items():
                if i == jr:
                    out.append(f'        ad{w} = {addr_c(s["addr"])};')
                elif i == jm:
                    out.append(f'        mk{w} = s{s["args"][0][2:-1]} + ({U})({s["args"][1]});')
                elif i == j:
                    out.append(f'        vv{w} = s{s["args"][0][2:-1]};')
            continue
        if k == 'write':
            if i in idiom:
                jr, jm, j = idiom[i]
                v = f'vv{i}'
                low, kind = MASKS[stmts[jm]['op']]
                pos = f'(((ad{i}) & SPU_LS_MASK & ~0xFu) + ((mk{i}) & 0x{low:X}u))'
                if kind == 'b':
                    out.append(f'        ls[{pos}] = (uint8_t){v};')
                elif kind == 'h':
                    out.append(f'        {{ const uint16_t hv = __builtin_bswap16((uint16_t){v}); memcpy(&ls[{pos}], &hv, 2); }}')
                else:
                    out.append(f'        {{ const {U} wv = __builtin_bswap32({v}); memcpy(&ls[{pos}], &wv, 4); }}')
            else:
                if s['src'] in written:
                    out.append(f'        R[{s["src"]}] = spu_splat_u32(s{s["src"]});')
                out.append(f'        spu_ls_write128_ls(ctx, ls, 0, {addr_c(s["addr"])}, R[{s["src"]}]);')
            continue
        r = s['dst']
        if k == 'read':
            out.append(f'        {{ {U} q; memcpy(&q, &ls[({addr_c(s["addr"])}) & SPU_LS_MASK & ~0xFu], 4); '
                       f's{r} = __builtin_bswap32(q); }}')
        else:
            out.append(f'        s{r} = {expr(s)};')
        if r in maybe and s['reg']:
            out.append(f'        w{r} = 1;')
    out.append('        ' + ('++nst; ' if back['chain'] else '') + '/* the back edge: the slice said it is taken */')
    out.append('    }')
    for r in sorted(carried):
        out.append(f'    R[{r}] = spu_splat_u32(s{r});')
    for r in sorted(maybe - carried):
        out.append(f'    if (w{r}) R[{r}] = spu_splat_u32(s{r});')
    out.append('}')
    return out


def scalarize(lines, log):
    """Rewrite every simple loop of a native body (lines as gen_native.translate returns them)."""
    out = list(lines)
    uid = 0
    i = 0
    while i < len(out):
        m = R_LABEL.match(out[i].strip())
        if not m:
            i += 1
            continue
        head = m.group(1)
        # the last back edge to this head
        end = None
        for k in range(i + 1, len(out)):
            t = out[k].strip()
            e = R_CHAIN.match(t) or R_GOTO.match(t)
            if e and e.group('lab') == head:
                end = k
        if end is None:
            i += 1
            continue
        uid += 1
        try:
            fast = scalar_loop([l.strip() for l in out[i:end + 1]], head, uid)
        except Refuse as ex:
            log(f'  loop {head}: left as is ({ex})')
            i += 1
            continue
        # entries from outside the loop go through the fast path
        for k in list(range(0, i)) + list(range(end + 1, len(out))):
            out[k] = out[k].replace(f'goto {head};', f'goto {head}_fast{uid};')
        out[i:i] = fast
        log(f'  loop {head}: scalar fast path ({end - i} statements)')
        i += len(fast) + 1
    return out
