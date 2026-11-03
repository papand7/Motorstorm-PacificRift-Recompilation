import collections, importlib.util, sys
from pathlib import Path
ROOT = Path('.').resolve()
spec = importlib.util.spec_from_file_location('jr', ROOT/'generated/analysis/t37/job_report.py'); jr = importlib.util.module_from_spec(spec); spec.loader.exec_module(jr)
jobs, extra = jr.parse(Path(sys.argv[1])/'ftrace.txt')
nm = jr.names(ROOT/'generated/analysis/t37/retail_jobs.json')
seq = []
for who, a, b, t0, t1 in sorted(jobs, key=lambda j: j[3]):
    x = extra.get((who, round(t1, 1)), {})
    seq.append((nm.get(x.get(28, (None,))[0], '?'), x.get(27, (0, 0))[0], t0, t1))
bursts, cur = [], []
for n, s, t0, t1 in seq:
    if n == 'renderablejob': cur.append((s, t0, t1))
    elif cur: bursts.append(cur); cur = []
print('bursts', len(bursts), 'len distribution', collections.Counter(len(b) for b in bursts).most_common(8))
for b in bursts[100:106]:
    print(' '.join(str(s) for s, *_ in b))
# position profile
pos = collections.defaultdict(list)
for b in bursts:
    for i, (s, *_ ) in enumerate(b): pos[i].append(s)
print('mean interp by position:', ' '.join(f'{i}:{sum(v)//len(v)}' for i, v in sorted(pos.items())[:40]))
# gap between consecutive runs vs interp
g = collections.defaultdict(list)
for b in bursts:
    for (s0, a0, e0), (s1, a1, e1) in zip(b, b[1:]):
        g['0' if s1 == 0 else '139' if s1 == 139 else 'big'].append(a1 - e0)
import statistics
print({k: (len(v), round(statistics.median(v), 1)) for k, v in g.items()}, 'median gap us before run, by class')
