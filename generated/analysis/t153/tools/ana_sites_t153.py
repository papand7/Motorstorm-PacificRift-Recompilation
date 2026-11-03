"""T153: per-call guest-site durations from the PT log (stderr.log `[PT] ... ev=exit fn=<site> dur_us=`).

  py -3 ana_sites_t153.py <ana_json> <run_dir>     adds "pt_sites" to <ana_json> (in place)

The T146-based exes have no T149 guest-function spans in cpath.txt, so the frame-end Wws spin 0x50C818
and the other once-per-frame sites are measured from the PT exit records instead. Window: race entry + 10 s
to race entry + 88 s (PT t is host us since process start; race entry from the controller, within ~1 s).
Only sites whose exit count stayed under their PT limit are complete; 'complete' says so (limit@ in
cpath_sites.cfg: 50C818/72E1E0/736770 20000, 4B63F0 2000, others 4000)."""
import json, re, statistics as S, sys
from pathlib import Path

SITES = {'0050C818': ('frame-end Wws spin', 20000), '0072E1E0': ('ref throttle', 20000),
         '00736770': ('PUT flush', 20000), '0030B710': ('Havok wait', 4000),
         '004AACA0': ('JobBatch Wait', 4000), '005F74B0': ('PVS WaitForCompletion', 4000)}
RX = re.compile(r'^\[PT\] t=(\d+) tid=\d+ ev=exit .*?fn=([0-9A-F]{8}) .*?dur_us=(\d+)')

ana, run_dir = Path(sys.argv[1]), Path(sys.argv[2])
d = json.loads(ana.read_text(encoding='utf-8'))
entry = d.get('race_entry_s')
rows = {k: [] for k in SITES}
total = {k: 0 for k in SITES}
with open(run_dir / 'stderr.log', encoding='utf-8', errors='replace') as f:
    for line in f:
        if not line.startswith('[PT] t='):
            continue
        m = RX.match(line)
        if not m or m[2] not in SITES:
            continue
        total[m[2]] += 1
        t = int(m[1]) / 1e6
        if entry is not None and entry + 10 <= t <= entry + 88:
            rows[m[2]].append(int(m[3]) / 1000.0)
out = {}
for k, (name, lim) in SITES.items():
    r = rows[k]
    out[k] = {'name': name, 'calls_in_window': len(r), 'complete': total[k] < lim,
              'mean_ms': round(S.mean(r), 2) if r else None, 'p50_ms': round(S.median(r), 2) if r else None,
              'sum_s': round(sum(r) / 1000.0, 2) if r else None}
d['pt_sites'] = out
ana.write_text(json.dumps(d, indent=1), encoding='utf-8')
print(ana.name, {k: (v['mean_ms'], v['calls_in_window'], v['complete']) for k, v in out.items()})
