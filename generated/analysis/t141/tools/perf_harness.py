"""T141: medians (and p90) of [rsx-frame-perf] fields from frame 50 on, per run dir.
usage: python perf_harness.py <run_dir>..."""
import sys, os, re, statistics
for run in sys.argv[1:]:
    v = {}
    for l in open(os.path.join(run, 'err.txt'), encoding='utf-8', errors='replace'):
        m = re.match(r'\[rsx-frame-perf\] gframe=(\d+)', l)
        if not m or int(m.group(1)) < 50: continue
        for k in ('rf_ms', 'record_ms', 'submit_ms', 'wait_ms', 'present_ms', 'wall_ms'):
            x = re.search(r'\b' + k + r'=([\d.]+)', l)
            if x: v.setdefault(k, []).append(float(x.group(1)))
    n = len(v.get('rf_ms', []))
    print(os.path.basename(run), n, {k: (round(statistics.median(a), 2), round(sorted(a)[int(len(a) * 0.9)], 2)) for k, a in v.items()})
