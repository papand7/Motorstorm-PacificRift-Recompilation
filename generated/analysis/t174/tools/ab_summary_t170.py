"""T170: per-arm medians from <dir>/<arm>_<rep>/err.txt (last 20 frames of each rep; median of reps, min-max in brackets)."""
import re, sys, pathlib, statistics as st
NUM = re.compile(r'([a-z_]+)=(-?[0-9.]+)')
K = 'wall_ms draw_cb_ms expand_ms record_ms tex_ms pso_ms cmd_ms submit_ms upload_mb'.split()
arms = {}
for d in sorted(pathlib.Path(sys.argv[1]).iterdir()):
    if not d.is_dir(): continue
    arm = d.name.rsplit('_', 1)[0]
    rows = []
    for l in open(d / 'err.txt', errors='replace'):
        if l.startswith('[rsx-frame-perf] gframe='):
            x = {}
            for k, v in NUM.findall(l.replace('[tex ', 'tex_ms=').replace('| pso ', 'pso_ms=').replace('| cmd ', 'cmd_ms=').replace(' n=', ' tn=', 1)):
                x.setdefault(k, float(v))
            rows.append(x)
    rows = rows[-20:]
    if rows:
        arms.setdefault(arm, []).append({k: st.median(r.get(k, 0) for r in rows) for k in K})
print('arm'.ljust(14) + ''.join(k.replace('_ms', '').rjust(20) for k in K))
for a, reps in arms.items():
    print(a.ljust(14) + ''.join(f"{st.median(r[k] for r in reps):8.1f} ({min(r[k] for r in reps):.0f}-{max(r[k] for r in reps):.0f})".rjust(20) for k in K))
