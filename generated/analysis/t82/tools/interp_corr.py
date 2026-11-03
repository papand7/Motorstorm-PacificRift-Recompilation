import collections, importlib.util, sys
from pathlib import Path
ROOT = Path('.').resolve()
spec = importlib.util.spec_from_file_location('jr', ROOT/'generated/analysis/t37/job_report.py'); jr = importlib.util.module_from_spec(spec); spec.loader.exec_module(jr)
jobs, extra = jr.parse(Path(sys.argv[1])/'ftrace.txt')
nm = jr.names(ROOT/'generated/analysis/t37/retail_jobs.json')
seq = []
for who, a, b, t0, t1 in sorted(jobs, key=lambda j: j[3]):
    x = extra.get((who, round(t1, 1)), {})
    mod = x.get(28, (None, 0))[0]
    seq.append((nm.get(mod, str(mod)), x.get(27, (0, 0))[0], x.get(29, (0, 0))[1], t0, t1, b >> 24))
cls = lambda s: '0' if s == 0 else '139' if s == 139 else '<2k' if s < 2000 else '2k-10k' if s < 10000 else '>=10k'
c = collections.Counter(); cp = collections.Counter(); cw = collections.Counter()
for i, (n, s, res, t0, t1, w) in enumerate(seq):
    if n != 'renderablejob': continue
    prev = seq[i-1][0] if i else '-'
    c[(cls(s), res)] += 1
    cp[(cls(s), prev)] += 1
print('class x aot_res(1 resident,2 installed):', sorted(c.items()))
print('class x previous job (global order):')
for k, v in sorted(cp.items(), key=lambda kv: (kv[0][0], -kv[1]))[:40]: print('  ', k, v)
# per-frame position: index of renderablejob within a burst
print('aot_res per module:')
r = collections.defaultdict(collections.Counter)
for n, s, res, *_ in seq: r[n][res] += 1
for n, v in sorted(r.items(), key=lambda kv: -sum(kv[1].values())): print('  ', n, dict(v))
