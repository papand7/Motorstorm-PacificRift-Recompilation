"""spunat2 generator: a native from lifted functions of a lift WITHOUT --chain-chunks (Wws relocatable
job modules, the Wws_Job policy module, plain images). Complements gen_native.py (chained groups).

  python gen_stitch.py <spu_recomp.c> <prefix> <image id> <out.c> --entry 0x40D8 [--entry ...]
         [--max-funcs 24] [--no-nx] [--fixall] [--mutate ...]

For each entry: the entry function and every function reachable from it through plain transfers
(`ctx->pc = X; g_spu_trampoline_fn = F; return;`), up to --max-funcs, are stitched into one native:
  - SPU registers in C locals (loaded once, written back at every exit: the registers the native writes);
  - LS through `ls` with the diagnostic gate off (the native declines while a diagnostic is armed);
  - a transfer to a stitched function is a goto when SPU_CHAIN_OK holds (one step, as SPU_CHAIN), else
    the native exits there with the transfer pending (the drain does the hop, the interrupt, ...);
  - a transfer elsewhere, SPU_RET / SPU_RET_REG: write back and exit exactly as the lifted code;
  - functions with host calls, channel access, stop/halt, indirect branches or interpreter hand-offs
    are not stitched: a transfer to them is an exit;
  - --nx (default): straight-line regions with single-precision arithmetic run speculatively in the
    x86 SPU mode of spu_nx.h; a region whose bad-lane mask is set is recomputed with the exact helpers
    from its saved inputs before anything it produced is used by a branch, a store or an exit.
Output: static int nat_<addr>(spu_context*) per entry and nat_register_all(); include it in the lift
through mkpair.py (LIFT(x) names the lift's symbols). Private (game-derived)."""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nxpass import nx_region, RE_DEF

ap = argparse.ArgumentParser()
ap.add_argument('src')
ap.add_argument('prefix')
ap.add_argument('image_id', type=int)
ap.add_argument('out')
ap.add_argument('--entry', action='append', required=True)
ap.add_argument('--max-funcs', type=int, default=24)
ap.add_argument('--no-nx', action='store_true')
ap.add_argument('--fixall', action='store_true')
ap.add_argument('--exclude', action='append', default=[], help='never stitch this function')
ap.add_argument('--mutate', default='', help='gate check: steps (one step short on the first absorbed hop)')
a = ap.parse_args()
P = a.prefix
text = Path(a.src).read_text(encoding='utf-8')
RE_FN = re.compile(r'^void ' + re.escape(P) + r'spu_func_([0-9A-F]{8})\(spu_context\* ctx\) \{$', re.M)
funcs = {}
for m in RE_FN.finditer(text):
    i = m.end() + 1
    j = text.index('\n}\n', i)
    funcs[int(m.group(1), 16)] = [l.strip() for l in text[i:j].split('\n')]
RE_TR = re.compile(r'\{ ctx->pc = (SPU_RA\()?(0x[0-9A-Fa-f]+)u?\)?; g_spu_trampoline_fn = ' + re.escape(P) +
                   r'spu_func_([0-9A-F]{8}); return; \}')
BAD = re.compile(r'spu_drain_call|spu_indirect_branch|SPU_IB_DISPATCH|spu_rdch|spu_wrch|spu_rchcnt|spu_stop|spu_halt|'
                 r'spu_unsupported|spu_interp|int_enable|host_depth|spu_native_entry|SPU_TAILCALL|stop_code|status')
reloc = 'SPU_RA(' in text


def stitchable(addr):
    if addr not in funcs or f'0x{addr:X}' in [e.upper().replace('0X', '0x') for e in a.exclude]:
        return False
    body = funcs[addr]
    for l in body:
        if BAD.search(l):
            return False
        if RE_TR.search(l):
            continue
        if re.search(re.escape(P) + r'spu_func_', l):
            return False
    return True


def closure(entry):
    order, todo = [], [entry]
    while todo and len(order) < a.max_funcs:
        f = todo.pop(0)
        if f in order or not stitchable(f):
            continue
        order.append(f)
        for l in funcs[f]:
            for m in RE_TR.finditer(l):
                t = int(m.group(3), 16)
                if t not in order:
                    todo.append(t)
    return order


def to_local(l):
    l = re.sub(r'spu_ls_read128\(ctx, ', 'spu_ls_read128_ls(ctx, ls, 0, ', l)
    l = re.sub(r'spu_ls_write128\(ctx, ', 'spu_ls_write128_ls(ctx, ls, 0, ', l)
    return re.sub(r'ctx->gpr\[(\d+)\]', r'R_\1', l)


def gen(entry):
    fs = closure(entry)
    if entry not in fs:
        sys.exit(f'0x{entry:X}: entry not stitchable')
    lines, used, written = [], set(), set()
    for f in fs:
        for l in funcs[f]:
            for r in re.findall(r'ctx->gpr\[(\d+)\]', l):
                used.add(int(r))
            m = re.match(r'ctx->gpr\[(\d+)\] = ', l)
            if m:
                written.add(int(m.group(1)))
    used |= {0}
    store = ' '.join(f'ctx->gpr[{r}] = R_{r};' for r in sorted(written))
    first_hop = [True]

    def ra(x):
        return f'SPU_RA({x}u)' if reloc else x

    def tr(m):
        tgt, fn = m.group(2), int(m.group(3), 16)
        if fn in fs:
            mut = ''
            if a.mutate == 'steps' and first_hop[0]:
                mut = ' --nst;'
                first_hop[0] = False
            return (f'{{ if (__builtin_expect(SPU_CHAIN_OK(ctx), 1)) {{ ++nst;{mut} goto F_{fn:08X}; }} '
                    f'EXIT_TR({ra(tgt)}, LIFT(spu_func_{fn:08X})); }}')
        return f'{{ EXIT_TR({ra(tgt)}, LIFT(spu_func_{fn:08X})); }}'

    for f in fs:
        lines.append(f'F_{f:08X}:')
        body = [l for l in funcs[f] if l and l not in ('/* nop */;', '/* branch hint (ignored) */;')]
        for l in body:
            if re.fullmatch(r'loc_[0-9A-F]{8}:', l):
                lines.append(f'L{f:08X}_{l[4:-1]}:')
                continue
            l = re.sub(r'goto loc_([0-9A-F]{8});', lambda m: f'goto L{f:08X}_{m.group(1)};', l)
            l = RE_TR.sub(tr, l)
            l = re.sub(r'SPU_RET\(ctx\);', 'EXIT_RET(0);', l)
            l = re.sub(r'SPU_RET_REG\(ctx, (\d+)\);', r'EXIT_RET(\1);', l)
            lines.append(to_local(l))
    nst_slots = 0
    if not a.no_nx:
        from nxpass import sink_stores
        lines, nst_slots = sink_stores(lines)
        lines = speculate(lines)
    regs = sorted(used | written)
    out = [f'/* stitched: {" ".join(f"0x{f:X}" for f in fs)} */',
           f'static int nat_{entry:08X}(spu_context* ctx)', '{',
           f'    SPU_FNREC(ctx, 0x{entry:X}u);',
           '    if (g_spu_ls_diag != 0 && (g_spu_ls_diag > 0 || spu_ls_diag_resolve())) return 0;',
           '    uint8_t* SPU_LS_RESTRICT ls = ctx->ls;',
           '    uint32_t nst = 0;',
           '    uint32_t _sta[NAT_ST_SLOTS]; u128 _stv[NAT_ST_SLOTS]; (void)_sta; (void)_stv;',
           '    u128 ' + ', '.join(f'R_{r} = ctx->gpr[{r}]' for r in regs) + ';']
    if not a.no_nx:
        out.append('    unsigned _csr, _csr0; NX_ENTER(_csr); (void)_csr0;')
        leave = 'NX_LEAVE(_csr); '
    else:
        leave = ''
    out.append(f'#define EXIT_TR(pc_, fn_) do {{ {leave}{store} ctx->steps += nst; ctx->pc = (pc_); '
               f'g_spu_trampoline_fn = (fn_); return 1; }} while (0)')
    out.append(f'#define EXIT_RET(n_) do {{ {leave}{store} ctx->steps += nst; ctx->pc = ctx->gpr[n_]._u32[0]; '
               f'if (ctx->host_depth == 0) g_spu_trampoline_fn = spu_indirect_branch; return 1; }} while (0)')
    out += ['    ' + l if not l.endswith(':') else l for l in lines]
    out += ['#undef EXIT_TR', '#undef EXIT_RET', '}', '']
    out = [x.replace('NAT_ST_SLOTS', str(max(1, nst_slots))) for x in out]
    return out, fs


def speculate(lines):
    """group consecutive pure register statements into regions; speculate the ones with FP arithmetic"""
    out, reg = [], []

    def flush():
        if not reg:
            return
        if any(re.search(r'\bspu_(fa|fs|fm|fma|fms|fnms)\(', l) for l in reg):
            rd, wr = set(), set()
            for l in reg:
                m = RE_DEF.match(l)
                rhs = m.group(3) if m else l
                for r in re.findall(r'\bR_(\d+)\b', rhs):
                    rd.add(int(r))
                if m:
                    wr.add(int(m.group(1)))
            sv = sorted(rd & wr)
            save = ' '.join(f'const u128 _s{r} = R_{r};' for r in sv)
            rest = ' '.join(f'R_{r} = _s{r};' for r in sv)
            fast = nx_region(reg, a.fixall)
            out.append('{ ' + save + ' __m128i _nxb = _mm_setzero_si128();')
            out.extend(fast)
            out.append(f'if (__builtin_expect({"0" if a.mutate == "nxflag" else "NX_ANY(_nxb)"}, 0)) {{ NX_LEAVE(_csr); {rest}')
            out.extend(reg)
            out.append('NX_ENTER(_csr0); } }')
        else:
            out.extend(reg)
        reg.clear()

    for l in lines:
        m = RE_DEF.match(l)
        if m or l.strip().startswith('_st'):
            reg.append(l)
        else:
            flush()
            out.append(l)
    flush()
    return out


hdr = [f'/* spunat2 GENERATED native (gen_stitch.py, image {a.image_id}); private (game-derived). */',
       f'#define NAT_IMG {a.image_id}', '#include <string.h>', '#include "../harness/spu_fnrec.h"']
if not a.no_nx:
    hdr += ['#pragma STDC FENV_ACCESS ON',
            '#pragma clang attribute push (__attribute__((target("avx2,fma"))), apply_to = function)',
            '#include "../harness/spu_nx.h"']
hdr += ['extern int spu_native_register(int image_id, uint32_t addr, int (*fn)(spu_context*));',
        'extern void spu_indirect_branch(spu_context* ctx);', '']
body, reg = [], ['static void nat_register_all(void) {']
for e in a.entry:
    e = int(e, 0)
    o, fs = gen(e)
    body += o
    reg.append(f'    spu_native_register({a.image_id}, 0x{e:X}u, nat_{e:08X});')
    print(f'entry 0x{e:X}: stitched {len(fs)} function(s): {" ".join(hex(f) for f in fs)}')
reg.append('}')
tail = ['#pragma clang attribute pop', '#pragma STDC FENV_ACCESS OFF'] if not a.no_nx else []
Path(a.out).write_text('\n'.join(hdr + body + reg + tail) + '\n', encoding='utf-8')
print('wrote', a.out)
