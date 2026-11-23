"""Attribute spu_task_replay prof samples: by host function, by inlined helper, and by SPU block
(the nearest loc_XXXXXXXX label / spu_func_ above the sampled spu_recomp.c line).
usage: python prof_report.py <exe> <samples> [top 30]"""
import collections, re, subprocess, sys
from pathlib import Path

EXE, SAMPLES = Path(sys.argv[1]), Path(sys.argv[2])
TOP = int(sys.argv[3]) if len(sys.argv) > 3 else 30
LLVM = Path(__file__).resolve().parents[4] / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin'
BASE = 0x140000000
rvas = [int(l, 16) for l in SAMPLES.read_text().split()]
cnt = collections.Counter(rvas)
addrs = sorted(cnt)
r = subprocess.run([str(LLVM / 'llvm-symbolizer.exe'), '--obj=' + str(EXE), '--inlining', '--functions=linkage',
                    '--output-style=LLVM'], input='\n'.join(hex(BASE + a) for a in addrs) + '\n',
                   capture_output=True, text=True)
recs = [b.split('\n') for b in r.stdout.strip('\n').split('\n\n')]
assert len(recs) == len(addrs), (len(recs), len(addrs))
files = {}
labels = {}


def block_of(path, line):
    if path not in labels:
        try:
            L = Path(path).read_text(errors='replace').split('\n')
        except OSError:
            L = []
        lab, cur = [], ''
        for t in L:
            m = re.match(r'(?:loc_([0-9A-F]{8}):|(?:static )?void \S*spu_(?:func|grp)_([0-9A-F]{8}))', t)
            if m:
                cur = m.group(1) or m.group(2)
            lab.append(cur)
        labels[path] = lab
    lab = labels[path]
    return lab[line - 1] if 0 < line <= len(lab) else '?'


total = len(rvas)
by_fn, by_leaf, by_blk = collections.Counter(), collections.Counter(), collections.Counter()
for a, rec in zip(addrs, recs):
    n = cnt[a]
    frames = [(rec[i], rec[i + 1]) for i in range(0, len(rec) - 1, 2)]
    outer = frames[-1][0]
    by_fn[re.sub(r'spu_[0-9a-f]{64}_', '', outer)] += n
    by_leaf[re.sub(r'spu_[0-9a-f]{64}_', '', frames[0][0])] += n
    for fn, loc in frames:
        m = re.match(r'(.*):(\d+):\d+$', loc)
        if m and m.group(1).endswith('spu_recomp.c'):
            by_blk[block_of(m.group(1), int(m.group(2)))] += n
            break
    else:
        by_blk['(outside lifted code)'] += n
for title, c in (('host function', by_fn), ('innermost (inlined) function', by_leaf), ('SPU block', by_blk)):
    print(f'== by {title} ({total} samples)')
    for k, v in c.most_common(TOP):
        print(f'{100.0 * v / total:6.2f}%  {k}')
