"""Generator: native C from one --chain-chunks group of a lifted SPU image (v2; supersedes
transl_native.py).

  python gen_native.py <spu_recomp.c> <image-id> <out.c> --entry loc_00010890 [--entry loc_...]

One native function per entry label: the group's statements from that label on, with
  - SPU registers as the local array R[] (loaded from ctx->gpr at entry, stored back at every exit);
  - LS through the lifted helpers with diagnostics off;
  - each SPU_CHAIN(_BACK) edge: a goto while chaining is open (same step count as the lifted code),
    otherwise the lifted failure branch (pc set, trampoline, exit) -- the budget is kept for _BACK;
  - channel reads/writes/rchcnt as calls (the runtime does not read gprs there, no flush);
  - halt/stop/unsupported calls after a register flush (they may read ctx->gpr);
  - a plain cross-group transfer (trampoline + return) and every other `return;` as a flushed exit
    that returns 1 (the hook's `return;` then completes the lifted function).
Refused (exit 2, the function stays lifted): spu_drain_call, spu_img_restore (nested host call),
spu_indirect_branch / SPU_RET / SPU_IB_DISPATCH (returns through the host frame), spu_native_entry,
spu_blockcount_dump, spu_snapshot_take, SPU_TAILCALL, calls to lifted functions.
Declines at run time (return 0): an LS diagnostic armed. Output is private (game-derived)."""
import argparse
import re
import sys
from pathlib import Path

REFUSE = re.compile(r'spu_drain_call|spu_img_restore|spu_indirect_branch\(|SPU_IB_DISPATCH|'
                    r'spu_native_entry|spu_blockcount_dump|spu_snapshot_take|SPU_TAILCALL|spu_func_[0-9A-Fa-f]{8}\(')
RE_RET = re.compile(r'SPU_RET(_REG)?\(ctx(?:, (\d+))?\);')
RE_GPR = re.compile(r'ctx->gpr\[(\d+)\]')
RE_CHAIN = re.compile(r'SPU_CHAIN(_BACK)?\(ctx, (0x[0-9A-Fa-f]+)u, (loc_[0-9A-Fa-f]{8}), ([A-Za-z0-9_]+)\);')
RE_LABEL = re.compile(r'loc_[0-9A-Fa-f]{8}:')
# every runtime call a replay (and a diagnostic) can observe the registers at: flush before it
FLUSH_CALLS = re.compile(r'(?<!void )(spu_(?:halt|stop|unsupported)\()')


def group_bounds(text, lab_idx):
    gstart = max(i for i in range(lab_idx) if text[i].startswith('static void ') and '_spu_grp_' in text[i])
    gend = next(i for i in range(lab_idx, len(text)) if text[i] == '}')
    return gstart, gend


def translate(body, fast=False):
    used, out, bad = {0, 1}, [], []   # the link and the stack are always loaded and stored
    for raw in body:
        t = raw.strip()
        if not t or t in ('/* nop */;', '/* branch hint (ignored) */;'):
            continue
        if RE_LABEL.fullmatch(t):
            out.append(t)
            continue
        if REFUSE.search(t):
            bad.append(t)
            continue
        for m in RE_GPR.finditer(t):
            used.add(int(m.group(1)))
        # SPU_RET and the exits read R[0] (the link) and the trampolines R[1] even when no
        # statement names them: they are always loaded and stored
        if 'SPU_RET' in t or 'spu_stop(' in t or 'g_spu_trampoline_fn' in t or 'return;' in t:
            used |= {0, 1}
        t = RE_GPR.sub(lambda m: f'R[{m.group(1)}]', t)

        def chain(m):
            back, tgt, lab, fn = m.group(1), m.group(2), m.group(3), m.group(4)
            budget = '--_budget && ' if back else ''
            # --fast: _ck (chaining open and interrupts off at entry, nothing in the body can change
            # either) makes every edge a plain goto; the budget only returns to the drain, which
            # resumes the same state, so it is skipped too
            ok = f'_ck || ({budget}SPU_CHAIN_OK(ctx))' if fast else f'{budget}SPU_CHAIN_OK(ctx)'
            return (f'{{ ctx->pc = {tgt}; if ({ok}) {{ ++nst; goto {lab}; }} '
                    f'STORE_ALL(); ctx->steps += nst; g_spu_trampoline_fn = {fn}; return 1; }}')
        t = RE_CHAIN.sub(chain, t)
        if 'g_spu_trampoline_fn' in t and 'SPU_CHAIN' not in t:
            t = re.sub(r'g_spu_trampoline_fn = ([A-Za-z0-9_]+); return;',
                       r'STORE_ALL(); ctx->steps += nst; g_spu_trampoline_fn = \1; return 1;', t)
        def ret(m):   # SPU_RET / SPU_RET_REG: a host return through r0 or the named link register
            n = m.group(2) or '0'
            return ('{ STORE_ALL(); ctx->steps += nst; ctx->pc = R[' + n + ']._u32[0]; '
                    'if (ctx->host_depth == 0) g_spu_trampoline_fn = spu_indirect_branch; return 1; }')
        t = RE_RET.sub(ret, t)
        # a channel call inside an expression (R[2] = spu_rdch(...)) is wrapped in a statement
        # expression, so the flush sits in front of the call and not inside the assignment
        t = re.sub(r'(spu_(?:rdch|rchcnt|wrch)\(ctx, [^;]*?\))(?=;)',
                   lambda m: '({ STORE_ALL(); ' + m.group(1) + '; })', t)
        t = FLUSH_CALLS.sub(lambda m: 'STORE_ALL(); ' + m.group(1), t)
        t = re.sub(r'(?<![A-Za-z_])return;', 'ctx->steps += nst; STORE_ALL(); return 1;', t)
        t = t.replace('/* nop */;', '')
        if t.strip():
            out.append(t)
    return out, used, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('image_id', type=int)
    ap.add_argument('out')
    ap.add_argument('--entry', action='append', required=True)
    ap.add_argument('--prefix', default='nat')
    ap.add_argument('--sym', default='', help='symbol prefix of the lift the natives link to (default: image dir name + _)')
    ap.add_argument('--fast', action='store_true',
                    help='hoist the chain check, restrict LS and scalar registers where the body allows it')
    ap.add_argument('--scalar', action='store_true',
                    help='with --fast: a lane-0 scalar fast path for simple loops (scalarize.py)')
    ap.add_argument('--dirty', action='store_true',
                    help='before a channel call store only the registers written since the last flush')
    ap.add_argument('--coverage', action='store_true',
                    help='count every label and exit hit (NAT_COVERAGE builds print them at exit)')
    a = ap.parse_args()
    text = Path(a.src).read_text(encoding='utf-8').split('\n')
    img = Path(a.src).parent.name
    fns, regs_all, errors = [], set(), []
    for ent in a.entry:
        lab_idx = next(i for i, l in enumerate(text) if l == ent + ':')
        _, gend = group_bounds(text, lab_idx)
        lines, used, bad = translate(text[lab_idx:gend], a.fast)
        if bad:
            errors += [f'{ent}: refused: {b}' for b in bad[:4]]
            continue
        regs_all |= used
        fname = f'{a.prefix}_{ent[4:]}'
        # a body that calls the runtime (channel ops: a DMA writes LS through ctx->ls, an event
        # can arrive) or changes int_enable keeps plain LS and the per-edge chain check
        calls = any(re.search(r'spu_(?:rdch|wrch|rchcnt)\(|int_enable', l) for l in lines)
        fast = a.fast and not calls
        if a.dirty:
            from dirty import dirty_flush
            lines = dirty_flush(lines)
        from dirty_exits import dirty_exits
        lines = dirty_exits(lines)
        if a.scalar and fast:
            from scalarize import scalarize
            lines = scalarize(lines, lambda m: print(f'{ent}:{m}'))
        pro = ['    uint32_t nst = 0;', '    int32_t _budget = SPU_CHAIN_BUDGET;',
               '    uint8_t* SPU_LS_RESTRICT ls = ctx->ls;' if fast else '    uint8_t* ls = ctx->ls;']
        if a.fast:
            pro.append('    const int _ck = ' + ('!ctx->int_enable && SPU_CHAIN_OK(ctx);' if fast else '0;'))
            pro.append('    (void)_ck;')
            # registers as separate locals: R[n] -> R_n
            lines = [re.sub(r'R\[(\d+)\]', r'R_\1', l) for l in lines]
            pro += [f'    u128 R_{n} = ctx->gpr[{n}];' for n in sorted(used)]
            store = ' '.join(f'ctx->gpr[{n}] = R_{n};' for n in sorted(used))
        else:
            pro.append('    u128 R[128];')
            pro += [f'    R[{n}] = ctx->gpr[{n}];' for n in sorted(used)]
            store = ' '.join(f'ctx->gpr[{n}] = R[{n}];' for n in sorted(used))
        body = lines
        if a.coverage:
            # every label and every exit counts its hits (NAT_COVERAGE builds print them at exit)
            sites, nb = [], []
            for l in body:
                if RE_LABEL.fullmatch(l):
                    sites.append(l[:-1])
                    nb.append(l)
                    nb.append(f'NATC_{fname}({len(sites) - 1});')
                    continue
                if re.search(r'(?<![A-Za-z_])return 1;', l):
                    k = len(sites); sites.append(f'exit@{k}')
                    l = re.sub(r'(?<![A-Za-z_])return 1;', f'{{ NATC_{fname}({k}); return 1; }}', l)
                nb.append(l)
            body = nb
            cov_decl = [f'#ifdef NAT_COVERAGE', f'static unsigned long long NATCOV_{fname}[{len(sites)}];',
                        f'static const char* const NATNAME_{fname}[{len(sites)}] = {{' +
                        ', '.join(f'"{s}"' for s in sites) + '};',
                        f'#define NATC_{fname}(i) (NATCOV_{fname}[i]++)',
                        f'void natcov_{fname}(void) {{ for (int i = 0; i < {len(sites)}; i++) '
                        f'if (NATCOV_{fname}[i]) fprintf(stderr, "NATCOV {fname} %s %llu\\n", NATNAME_{fname}[i], '
                        f'NATCOV_{fname}[i]); }}',
                        f'#define NATCOV_FNAME_{fname} 1',
                        '#else', f'#define NATC_{fname}(i) ((void)0)', '#endif']
            fns += cov_decl
        fns += [f'static int {fname}(spu_context* ctx) {{',
                '    /* decline: an LS diagnostic is armed (the lifted gate would report what this skips) */',
                '    if (g_spu_ls_diag != 0 && (g_spu_ls_diag > 0 || spu_ls_diag_resolve())) return 0;',
                *pro,
                f'#define STORE_ALL() do {{ {store} }} while (0)',
                *['    ' + l if not RE_LABEL.fullmatch(l) else l for l in body],
                '#undef STORE_ALL', '}', '']
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        sys.exit(2)
    hdr = [f'/* Native rewrite (gen_native.py from {img}, image {a.image_id}). Private: derived from the',
           ' * game\'s SPU code. PS3_SPU_NATIVE=0 turns it off. */',
           '#include <stdio.h>', '#include <string.h>', '#include "spu_context.h"', '#include "spu_helpers.h"',
           'extern void spu_stop(spu_context*);', 'extern void spu_halt(spu_context*);',
           'extern void spu_unsupported(uint32_t, const char*);',
           'extern u128 spu_rdch(spu_context*, uint32_t);', 'extern uint32_t spu_rchcnt(spu_context*, uint32_t);',
           'extern void spu_wrch(spu_context*, uint32_t, u128);',
           'extern int spu_native_register(int image_id, uint32_t addr, int (*fn)(spu_context*));',
           'extern void spu_indirect_branch(spu_context* ctx);', '']
    sym = a.sym or f'{img}_'   # the symbol prefix of the lift these natives link to
    reg = [f'void {sym}spu_natives_register(void) {{']
    for ent in a.entry:
        reg.append(f'    spu_native_register({a.image_id}, 0x{int(ent[4:], 16):X}u, {a.prefix}_{ent[4:]});')
    reg.append('}')
    if a.coverage:
        # the replay calls this once at the end (NAT_COVERAGE builds): a destructor crashed at exit
        names = [e[4:] for e in a.entry]
        reg += ['#ifdef NAT_COVERAGE', 'void nat_coverage_dump(void) {'] + \
               [f'    natcov_{a.prefix}_{n}();' for n in names] + ['}', '#endif']
    text_out = '\n'.join(hdr + fns + reg) + '\n'
    text_out = text_out.replace(f'{img}_', sym)   # the lift's own symbols (spu_func_*, spu_grp_*)
    Path(a.out).write_text(text_out, encoding='utf-8')
    print(f'wrote {a.out}: {len(a.entry)} entry(ies), {len(regs_all)} registers')


if __name__ == '__main__':
    main()
