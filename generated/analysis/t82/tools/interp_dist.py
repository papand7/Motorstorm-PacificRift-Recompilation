#!/usr/bin/env python3
"""T82: per-run interpreted-instruction distribution (ftrace kind 27) per WWS module, from a
PS3_FTRACE_SPUJOB trace (read-only). Joins 26/27/28 by (lane, end time) exactly as t37/job_report.py.

  py -3 -I interp_dist.py <run dir> [module name ...]"""
import collections, importlib.util, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('jr', ROOT / 'generated' / 'analysis' / 't37' / 'job_report.py')
jr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jr)


def main(rd, want):
    jobs, extra = jr.parse(Path(rd) / 'ftrace.txt')
    nm = jr.names(ROOT / 'generated' / 'analysis' / 't37' / 'retail_jobs.json')
    by = collections.defaultdict(list)
    for who, a, b, t0, t1 in jobs:
        x = extra.get((who, round(t1, 1)), {})
        mod = x.get(28, (None, 0))[0]
        name = nm.get(mod, f'{mod}') if mod is not None else f'id {a:08X}'
        by[name].append((x.get(27, (0, 0))[0], t1 - t0))
    for name, v in sorted(by.items(), key=lambda kv: -sum(s for s, _ in kv[1])):
        if want and name not in want:
            continue
        s = sorted(x for x, _ in v)
        n = len(s)
        zero = sum(1 for x in s if x == 0)
        q = lambda p: s[min(n - 1, int(p * (n - 1)))]
        print(f'{name:28s} runs {n:6d} interp total {sum(s):12d} zero-runs {zero:6d} '
              f'p10 {q(.1):7d} p50 {q(.5):7d} p90 {q(.9):7d} p99 {q(.99):7d} max {s[-1]:8d}')
        if want:
            hist = collections.Counter((x // 1000) * 1000 for x in s)
            print('  histogram (1k buckets, top 25):', ' '.join(f'{k}:{c}' for k, c in sorted(hist.items())[:25]))
            small = collections.Counter(x for x in s if x < 2000)
            print('  most common exact values <2000:', small.most_common(15))
            # does interpretation correlate with duration?
            dz = [d for x, d in v if x == 0]
            dn = [d for x, d in v if x > 0]
            if dz and dn:
                print(f'  median us: runs with 0 interp {statistics.median(dz):.0f}, with >0 {statistics.median(dn):.0f}')


if __name__ == '__main__':
    main(sys.argv[1], set(sys.argv[2:]))
