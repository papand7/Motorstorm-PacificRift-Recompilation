"""Private (ppuopt): per-arm geomeans and per-function speedups (with noise bands) from wl2 results."""
import json
import statistics
import sys
from pathlib import Path

SETS = [('hot (session A)', [r'D:/motorstorm/ppuopt_scratch/wl2_hot/results.json']),
        ('hot (session B)', [r'D:/motorstorm/ppuopt_scratch/wl2_hot2/results.json']),
        ('prior21 (session A)', [r'D:/motorstorm/ppuopt_scratch/wl2_p21/results.json'])]
out = {}
for title, files in SETS:
    rows = []
    for f in files:
        if Path(f).exists():
            rows += json.loads(Path(f).read_text())
    if not rows:
        continue
    arms = [a for a in rows[0]['min'] if a != 'B']
    print(f'== {title}: {len(rows)} functions')
    res = {}
    for a in arms:
        sp, sig_up, sig_down, tb, ta = [], [], [], 0.0, 0.0
        for r in rows:
            if a not in r['min']:
                continue
            s = r['min']['B'] / r['min'][a]
            noise = max(r['cv']['B'], r['cv'][a])
            sp.append(s)
            tb += r['min']['B']
            ta += r['min'][a]
            if abs(s - 1) > max(0.02, 2 * noise):
                (sig_up if s > 1 else sig_down).append(f"{r['fn'][5:]}:{s:.2f}")
        g = statistics.geometric_mean(sp)
        res[a] = {'geomean': round(g, 3), 'n': len(sp), 'min': round(min(sp), 3), 'max': round(max(sp), 3),
                  'time_weighted': round(tb / ta, 3), 'faster': sig_up, 'slower': sig_down}
        print(f"  {a}: geomean {g:.3f} (min {min(sp):.3f} max {max(sp):.3f}); time-weighted {tb / ta:.3f}; "
              f"outside noise: {len(sig_up)} faster {sig_up}, {len(sig_down)} slower {sig_down}")
    out[title] = res
Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
