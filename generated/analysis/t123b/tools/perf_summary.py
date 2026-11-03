"""T123B: summarize logs/perf/*.log (perf_arms.py) per load and mode: medians over seeds."""
import re, statistics as st
from pathlib import Path
L = Path(__file__).resolve().parents[1] / 'logs/perf'
rows = {}
for f in sorted(L.glob('*.log')):
    load, m, _ = f.stem.rsplit('_', 2)
    t = f.read_text(encoding='utf-8', errors='replace')
    d = rows.setdefault((load, m), {})
    for sec in ('timing', 'producers'):
        g = re.search(rf'  {sec}\s+kicks (\d+)  kick->done p50 (\d+) p95 (\d+) p99 (\d+) max (\d+) us  >500us (\d+) .* wall (\d+) ms  cpu (\d+) Mcyc', t)
        for k, v in zip(('p50', 'p95', 'p99', 'max', 'late', 'wall', 'cpu'), g.groups()[1:]):
            d.setdefault(f'{sec}_{k}', []).append(float(v))
    g = re.search(r'  uncovered\s+kicks \d+  kick->done p50 (\d+)', t); d.setdefault('unc_p50', []).append(float(g.group(1)))
    g = re.search(r'  idle .*passes \d+ \((\d+)/s\), policy runs (\d+), process cpu ([\d.]+) Mcyc', t)
    d.setdefault('idle_pass', []).append(float(g.group(1))); d.setdefault('idle_runs', []).append(float(g.group(2)))
    d.setdefault('idle_cpu', []).append(float(g.group(3)))
    # coordinator stats windows (1 s): wakes/s, productive share, worker empty wakes, coord cpu
    for w in re.finditer(r'wakes/s=(\d+) timeout=(\d+) signal=(\d+) passes=(\d+) productive=(\d+) .*?worker_wakes=(\d+) worker_empty=(\d+) .*?coord_mcyc=([\d.]+)', t):
        ws, to, sg, ps, pr, wk, we, cc = map(float, w.groups())
        if ps < 50: continue
        d.setdefault('st_wakes', []).append(ws); d.setdefault('st_prod', []).append(pr / ps)
        d.setdefault('st_empty', []).append(we / max(wk, 1)); d.setdefault('st_ccpu', []).append(cc)
med = lambda d, k: st.median(d[k]) if d.get(k) else float('nan')
print('| load | arm | timing p50/p95/p99 us | >500us /400 | producers p50/p95/p99 us | >500us /800 | uncovered p50 us | idle passes/s | idle PM runs/s | idle CPU Mcyc/s | coord wakes/s (busy windows) | productive passes | empty worker wakes | coord CPU Mcyc/s |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for (load, m), d in sorted(rows.items()):
    print(f"| {load} | {m} | {med(d,'timing_p50'):.0f}/{med(d,'timing_p95'):.0f}/{med(d,'timing_p99'):.0f} | {med(d,'timing_late'):.0f} | "
          f"{med(d,'producers_p50'):.0f}/{med(d,'producers_p95'):.0f}/{med(d,'producers_p99'):.0f} | {med(d,'producers_late'):.0f} | "
          f"{med(d,'unc_p50'):.0f} | {med(d,'idle_pass'):.0f} | {med(d,'idle_runs'):.0f} | {med(d,'idle_cpu'):.1f} | "
          f"{med(d,'st_wakes'):.0f} | {med(d,'st_prod')*100:.0f}% | {med(d,'st_empty')*100:.0f}% | {med(d,'st_ccpu'):.1f} |")
print('\nper-section CPU (Mcyc, median): ' + '; '.join(f"{l} {m}: timing {med(d,'timing_cpu'):.0f} producers {med(d,'producers_cpu'):.0f}" for (l, m), d in sorted(rows.items())))
