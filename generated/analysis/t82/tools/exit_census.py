#!/usr/bin/env python3
"""T82: static census of every point where lifted WWS job code leaves straight-line native execution,
per module, from the lifted TUs (read-only). Counts, per module:
  word      `.word ...: not lifted -> interpreter` hand-offs (an undecodable word; the job continues in the
            interpreter from it if it is ever executed)
  unres     unresolved-branch hand-offs
  ib_ied    bie/bid/... indirect branches (interrupt-window fences) -> spu_indirect_branch
  ib_plain  other computed `bi $rX` (switch tables, computed jumps) -> spu_indirect_branch
  bisl      indirect calls (host bracket + spu_indirect_branch)
  ret_reg   `bi $rN` (N != 0) lifted as a host return through link rN (SPU_RET_REG)
  ib_cond   conditional computed branches (biz/binz... on a non-r0 target)
  iret      interrupt returns
  py -3 -I exit_census.py <lift dir> [<lift dir>]"""
import re, sys
from pathlib import Path

PAT = {
    'word': re.compile(r'/\* \.word [^*]*: not lifted -> interpreter \*/'),
    'unres': re.compile(r'/\* unresolved branch -> interpreter \*/'),
    'ib_ied': re.compile(r'ctx->int_enable = [01]; ctx->pc = ctx->gpr\[\d+\]\._u32\[0\]; g_spu_trampoline_fn = spu_indirect_branch; return;'),
    'ib_plain': re.compile(r'^\s*ctx->pc = ctx->gpr\[\d+\]\._u32\[0\]; g_spu_trampoline_fn = spu_indirect_branch; return;', re.M),
    'bisl': re.compile(r'ctx->host_depth\+\+; spu_indirect_branch\(ctx\);'),
    'ret_reg': re.compile(r'SPU_RET_REG\(ctx, \d+\)'),
    'ib_cond': re.compile(r'if \([^)]*\) \{ (?:ctx->int_enable = [01]; )?ctx->pc = ctx->gpr\[\d+\]\._u32\[0\]; g_spu_trampoline_fn = spu_indirect_branch; return; \}'),
    'iret': re.compile(r'ctx->pc = ctx->srr0; g_spu_trampoline_fn = spu_indirect_branch;'),
}


def census(d):
    import json
    man = {m['file'][:-4]: m.get('name') or m['file'] for m in json.load(open(Path(d) / 'wws_reloc_manifest.json'))}
    rows = {}
    for c in sorted(Path(d).glob('ms_*/spu_recomp.c')):
        s = c.read_text(errors='replace')
        rows[man.get(c.parent.name, c.parent.name)] = {k: len(p.findall(s)) for k, p in PAT.items()}
    return rows


def main():
    a = census(sys.argv[1])
    b = census(sys.argv[2]) if len(sys.argv) > 2 else None
    keys = list(PAT)
    print('| module | ' + ' | '.join(keys) + ' |' + (' changed by T82 |' if b else ''))
    print('|---' * (len(keys) + 1 + (1 if b else 0)) + '|')
    tot = {k: 0 for k in keys}
    for n, r in sorted(a.items(), key=lambda kv: -sum(kv[1].values())):
        for k in keys: tot[k] += r[k]
        ch = ''
        if b:
            d = {k: b[n][k] - r[k] for k in keys if b[n][k] != r[k]}
            ch = ' ' + (', '.join(f'{k} {v:+d}' for k, v in d.items()) or '-') + ' |'
        print(f'| {n} | ' + ' | '.join(str(r[k]) for k in keys) + ' |' + ch)
    print('| **total** | ' + ' | '.join(str(tot[k]) for k in keys) + ' |' + (' |' if b else ''))


if __name__ == '__main__':
    main()
