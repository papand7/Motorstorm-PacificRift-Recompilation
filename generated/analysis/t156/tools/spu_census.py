"""T156: static census of lifted SPU task images (spu_recomp.c), by class of generated construct.

  py -3 spu_census.py <label>=<spu_recomp.c> ...

Counts per image: lifted functions, block exits through the drain trampoline (g_spu_trampoline_fn),
in-function gotos, brsl calls (spu_drain_call), indirect branches, channel reads/writes by channel,
LS loads/stores, float ops, shuffles/rotates, and register-file traffic (ctx->gpr assignments).
Static counts only: they rank mechanisms, they are not a dynamic profile."""
import re
import sys
from collections import Counter

FLOAT = {'fa', 'fs', 'fm', 'fma', 'fms', 'fnms', 'fi', 'frest', 'frsqest', 'fcgt', 'fcmgt', 'fceq', 'fcmeq',
         'dfa', 'dfs', 'dfm', 'dfma', 'dfms', 'dfnms', 'csflt', 'cflts', 'cuflt', 'cfltu', 'fesd', 'frds'}
SHUF = {'shufb', 'rotqby', 'rotqbyi', 'shlqby', 'shlqbyi', 'rotqmby', 'rotqmbyi', 'rotqbi', 'shlqbi',
        'rotqmbi', 'cbd', 'chd', 'cwd', 'cdd', 'cbx', 'chx', 'cwx', 'cdx', 'fsmbi', 'fsmb', 'gb', 'gbh', 'gbb'}
CH = {0: 'SPU_RdEventStat', 1: 'SPU_WrEventMask', 2: 'SPU_WrEventAck', 3: 'SPU_RdSigNotify1', 4: 'SPU_RdSigNotify2',
      7: 'SPU_WrDec', 8: 'SPU_RdDec', 16: 'MFC_LSA', 17: 'MFC_EAH', 18: 'MFC_EAL', 19: 'MFC_Size', 20: 'MFC_TagID',
      21: 'MFC_Cmd', 22: 'MFC_WrTagMask', 23: 'MFC_WrTagUpdate', 24: 'MFC_RdTagStat', 25: 'MFC_RdListStallStat',
      26: 'MFC_WrListStallAck', 27: 'MFC_RdAtomicStat', 28: 'SPU_WrOutMbox', 29: 'SPU_RdInMbox', 30: 'SPU_WrOutIntrMbox'}

for arg in sys.argv[1:]:
    label, path = arg.split('=', 1)
    t = open(path, encoding='utf-8', errors='replace').read()
    ops = Counter(re.findall(r'\bspu_([a-z0-9_]+)\(', t))
    fl = sum(n for k, n in ops.items() if k in FLOAT)
    sh = sum(n for k, n in ops.items() if k in SHUF)
    wr = Counter(c for c in re.findall(r'spu_wrch\(ctx,\s*(\w+)', t))
    rd = Counter(c for c in re.findall(r'spu_rdch\(ctx,\s*(\w+)', t))
    funcs = len(re.findall(r'^void \w+_spu_func_[0-9A-F]+\(spu_context\* ctx\) \{', t, re.M))
    tramp = t.count('g_spu_trampoline_fn = ')
    gotos = len(re.findall(r'\bgoto loc_', t))
    ind = len(re.findall(r'spu_indirect_branch\w*\(', t))
    gpr = len(re.findall(r'ctx->gpr\[\d+\] = ', t))
    stmts = len(re.findall(r';\s*$', t, re.M))
    print(f'## {label} ({path.split("/")[-2] if "/" in path else path})')
    print(f'functions {funcs}, statements {stmts}, ctx->gpr assignments {gpr}')
    print(f'block exits via trampoline {tramp}, in-function gotos {gotos}, brsl calls (spu_drain_call) {ops["drain_call"]}, '
          f'indirect branches {ind}')
    print(f'LS loads {ops["ls_read128"]}, LS stores {ops["ls_write128"]}, float ops {fl}, shuffles/rotates/masks {sh}')
    print('channel writes: ' + ', '.join(f'{c} {n}' for c, n in wr.most_common()))
    print('channel reads: ' + ', '.join(f'{c} {n}' for c, n in rd.most_common()))
    print('top helpers: ' + ', '.join(f'{k} {n}' for k, n in ops.most_common(16)))
    print()
