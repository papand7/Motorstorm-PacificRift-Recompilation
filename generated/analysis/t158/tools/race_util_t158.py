"""T158: CPU and SPU-worker utilisation over the light race window (race frames 40..500).
  py -3 race_util_t158.py <run_dir> ...       prints JSON
Host clock = the latest [rsx-hb] ms= seen while streaming stderr.log (1 s resolution); race frame 0 = first
[rsx-frame-perf] with draw_calls >= 200. [spurs-busy] busy_ms per SPURS instance summed over the window,
divided by window length = average busy workers. performance.json samples (about 5 s apart, cumulative
process user+kernel CPU) inside the window give process CPU cores; per-thread CPU rows give the busiest threads (map tids with the H lines of cpath.txt)."""
import json, re, sys
from pathlib import Path
from collections import defaultdict
BUSY = re.compile(r'^\[spurs-busy\] spurs=(\S+) sn=(\d+) .*?busy_ms=([0-9.]+)')
out = {}
for rd in map(Path, sys.argv[1:]):
    hb, idx, t40, t500 = 0, None, None, None
    busy = defaultdict(float)
    buf = []
    for l in open(rd / 'stderr.log', encoding='utf-8', errors='replace'):
        if l.startswith('[rsx-hb] ms='):
            hb = int(l.split('ms=')[1].split()[0])
        elif l.startswith('[rsx-frame-perf] gframe='):
            m = re.search(r'draw_calls=(\d+)', l)
            if idx is None and m and int(m[1]) >= 200:
                idx = 0
            elif idx is not None:
                idx += 1
            if idx == 40: t40 = hb
            if idx == 500: t500 = hb
        elif l.startswith('[spurs-busy]') and t40 is not None and t500 is None:
            m = BUSY.match(l)
            if m: busy[m[1]] += float(m[3])
    win = (t500 - t40) / 1000
    perf = json.loads((rd / 'performance.json').read_text())
    ss = [s for s in perf['samples'] if t40 / 1000 <= s['t'] <= t500 / 1000]
    cpu = None
    if len(ss) >= 2:
        a, b = ss[0], ss[-1]
        cpu = round((b['cpu_user_s'] + b['cpu_kernel_s'] - a['cpu_user_s'] - a['cpu_kernel_s']) / (b['t'] - a['t']), 2)
    th = defaultdict(float)
    for s in ss[1:]:
        for tid, c in s['top_thread_cpu_s']:
            th[tid] += c
    span = (ss[-1]['t'] - ss[0]['t']) if len(ss) >= 2 else None
    out[rd.name] = {'window_host_s': [t40 / 1000, t500 / 1000], 'cpu_cores_busy': cpu, 'samples': len(ss),
                    'spurs_busy_workers': {k: round(v / 1000 / win, 2) for k, v in busy.items()},
                    'top_threads_cores': {str(t): round(c / span, 2) for t, c in sorted(th.items(), key=lambda x: -x[1])[:6]} if span else None}
print(json.dumps(out, indent=1))
