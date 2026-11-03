"""T143: one row per arm log: harness frame wall + CPU split, and the [gpu-prof] reports (report 0 dropped: warm-up)
averaged: mean and p95 per time, mean per count.   py -3 summ.py logs/bench/<round>"""
import re, sys, pathlib, collections
d = pathlib.Path(sys.argv[1])
keys = ['cpu_rf', 'cpu_pre', 'cpu_srv', 'cpu_loop', 'cpu_post', 'cpu_submit', 'cpu_present', 'gpu_total', 'gpu_loop', 'gpu_idle']
cnts = ['draw', 'pso_set', 'pso_skip', 'table', 'table_skip', 'cbv', 'cbv_skip', 'viewport', 'vp_skip', 'srv_create', 'srv_reuse', 'barrier', 'res_create', 'wait']
print('arm', 'wall_p50', 'wall_p95', 'cb_draw', 'cb_notify', 'cb_tex', 'cb_present', *[k + '(mean/p95)' for k in keys], sep='\t')
for f in sorted(d.glob('*.txt')):
    t = f.read_text(errors='replace')
    m = re.search(r'frame wall p50 ([\d.]+) p95 ([\d.]+)', t)
    c = re.search(r'draw callbacks ([\d.]+), state notify ([\d.]+), texture binds ([\d.]+), present ([\d.]+)', t)
    reps = re.split(r'\[gpu-prof\] report \d+:', t)[2:]
    acc = collections.defaultdict(list); cacc = collections.defaultdict(list)
    for r in reps:
        for k, mean, p95 in re.findall(r'\[gpu-prof\]\s+(\w+)\s+mean\s+([\d.]+)\s+p50\s+[\d.]+\s+p95\s+([\d.]+)', r):
            acc[k].append((float(mean), float(p95)))
        cl = re.search(r'counts/frame:(.*)', r)
        if cl:
            for k, v in re.findall(r'(\w+)=([\d.]+)', cl.group(1)): cacc[k].append(float(v))
    avg = lambda L, i: sum(x[i] for x in L) / len(L) if L else float('nan')
    row = [f.stem, m and m.group(1), m and m.group(2), *(c.groups() if c else ['-'] * 4)]
    row += [f'{avg(acc[k], 0):.3f}/{avg(acc[k], 1):.3f}' if acc[k] else '-' for k in keys]
    print(*row, sep='\t')
    if cacc: print('   counts:', ' '.join(f'{k}={sum(cacc[k]) / len(cacc[k]):.0f}' for k in cnts if cacc.get(k)))
