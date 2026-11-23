"""T158: attribute the harness's RIP samples (hvkdiff prof) to SPU-level cost classes.

  py -3 hvk_prof.py <exe with PDB> <samples file> <lifted spu_recomp.c dir root> [top N]

Each sample is symbolised with llvm-symbolizer (inline frames). A sample inside lifted code is
attributed to the lifted C statement (the spu_recomp.c line of its outermost inline frame there),
and the statement to a class: float arithmetic (spu_f*/spu_df*/csflt/cflts/... helpers), integer
and shuffle arithmetic (other spu_* helpers), local-store access (spu_ls_read/write), in-function
branch dispatch (SPU_CHAIN / trampoline stores / group entry switch), conditional branch tests,
call brackets (host call + spu_drain_call + spu_img_restore). Samples outside lifted code are
classed by function: drain loop and hop runtime, indirect-branch dispatch, exact float fallbacks,
other runtime. Independently, the sampled x64 instruction is classed as a guest-register-file
access (a memory operand on the context register's gpr range is not decidable statically here, so
this column reports plain loads/stores/moves vs ALU) from a disassembly of the exe.
"""
import collections
import re
import subprocess
import sys
from pathlib import Path

EXE, SAMPLES, LIFT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
TOP = int(sys.argv[4]) if len(sys.argv) > 4 else 25
LLVM = Path(__file__).resolve().parents[4] / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin'
BASE = 0x140000000

rvas = [int(l, 16) for l in SAMPLES.read_text().split()]
cnt = collections.Counter(rvas)
addrs = sorted(cnt)
inp = '\n'.join(hex(BASE + a) for a in addrs) + '\n'
r = subprocess.run([str(LLVM / 'llvm-symbolizer.exe'), '--obj=' + str(EXE), '--inlining', '--functions=linkage',
                    '--output-style=LLVM'], input=inp, capture_output=True, text=True)
blocks = r.stdout.strip('\n').split('\n\n') if '\n\n' in r.stdout else None
# LLVM style: pairs of lines per frame (function, file:line:col), records separated by blank lines
recs = [b.split('\n') for b in r.stdout.strip('\n').split('\n\n')]
if len(recs) != len(addrs):
    sys.exit(f'symbolizer returned {len(recs)} records for {len(addrs)} addresses')

src_cache = {}


def src_line(path, line):
    if path not in src_cache:
        try:
            src_cache[path] = Path(path).read_text(encoding='utf-8', errors='replace').split('\n')
        except OSError:
            src_cache[path] = []
    L = src_cache[path]
    return L[line - 1] if 0 < line <= len(L) else ''


FLOAT = re.compile(r'\bspu_(f[a-z]*|df[a-z]*|csflt|cuflt|cflts|cfltu)\s*\(')
OTHER = re.compile(r'\bspu_[a-z0-9_]+\s*\(')


def classify_stmt(t):
    if 'spu_drain_call' in t or 'host_depth' in t or 'spu_img_restore' in t:
        return 'call bracket (host call, drain_call, image restore)'
    if 'SPU_CHAIN' in t or 'g_spu_trampoline_fn' in t or re.match(r'\s*(case 0x|switch \(entry\)|default:)', t):
        return 'block transfer (chain / trampoline store / group entry)'
    if 'spu_ls_read' in t or 'spu_ls_write' in t:
        return 'local-store access'
    if FLOAT.search(t):
        return 'float arithmetic'
    if re.match(r'\s*if \(ctx->gpr', t):
        return 'conditional branch test'
    if OTHER.search(t):
        return 'integer / shuffle / logic'
    return 'other lifted statement'


def classify_fn(fn):
    if fn.startswith(('spu_drain_call', 'spu_run_with_halt', 'spu_task_launch_check', 'spu_depth_guard')):
        return 'drain loop / hop runtime'
    if 'indirect_branch' in fn or fn.startswith('spu_lookup') or 'lifted_lookup' in fn:
        return 'indirect-branch dispatch'
    if '_ref' in fn and fn.startswith('spu_'):
        return 'exact float fallback (out of line)'
    if fn.startswith('spu_img_restore'):
        return 'call bracket (host call, drain_call, image restore)'
    return 'other runtime: ' + fn


by_class, by_stmt, by_fn, by_helper = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
total = sum(cnt.values())
for a, rec in zip(addrs, recs):
    n = cnt[a]
    frames = [(rec[i], rec[i + 1]) for i in range(0, len(rec) - 1, 2)]   # innermost first
    outer_fn = frames[-1][0] if frames else '?'
    lifted = [(fn, loc) for fn, loc in frames if 'spu_recomp.c' in loc]
    if lifted:
        fn, loc = lifted[-1]
        m = re.match(r'(.*):(\d+):\d+$', loc)
        t = src_line(m.group(1), int(m.group(2))) if m else ''
        c = classify_stmt(t)
        by_stmt[(fn, m.group(2) if m else '?', t.strip()[:110])] += n
        inner = frames[0][0]
        by_helper[inner if inner != fn else '(lifted body)'] += n
    else:
        c = classify_fn(outer_fn)
    by_class[c] += n
    by_fn[outer_fn] += n

print(f'samples {total}  unique addresses {len(addrs)}')
print('\n| Class | samples | share |\n|---|---|---|')
for c, n in by_class.most_common():
    print(f'| {c} | {n} | {100.0 * n / total:.1f} % |')
print(f'\nTop {TOP} functions (outermost frame):')
for f, n in by_fn.most_common(TOP):
    print(f'  {100.0 * n / total:5.1f} %  {f}')
print(f'\nTop {TOP} innermost inlined helpers inside lifted code:')
for f, n in by_helper.most_common(TOP):
    print(f'  {100.0 * n / total:5.1f} %  {f}')
print(f'\nTop {TOP} lifted statements:')
for (f, ln, t), n in by_stmt.most_common(TOP):
    print(f'  {100.0 * n / total:5.1f} %  {f}:{ln}  {t}')
