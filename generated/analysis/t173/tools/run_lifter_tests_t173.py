"""Run the lifter and PPU tool tests in the baseline (T170) and fixed (T173) ps3recomp trees and compare exit codes.
usage: run_lifter_tests_t173.py <baseline tree> <fixed tree> <out json>"""
import json, subprocess, sys, time
from pathlib import Path

trees = {'base': Path(sys.argv[1]), 'fixed': Path(sys.argv[2])}
names = sorted({p.name for t in trees.values() for pat in ('test_ppu*.py', 'test_lifter*.py') for p in (t / 'tools').glob(pat)})
res = {}
for n in names:
    res[n] = {}
    for k, t in trees.items():
        p = t / 'tools' / n
        if not p.exists():
            res[n][k] = {'rc': None, 'note': 'absent'}
            continue
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, str(p)], cwd=t, capture_output=True, text=True, timeout=900)
            out = (r.stdout + r.stderr).strip().splitlines()
            res[n][k] = {'rc': r.returncode, 's': round(time.time() - t0, 1), 'tail': out[-2:] if out else [],
                         'skipped': any('SKIPPED' in l for l in out)}
        except subprocess.TimeoutExpired:
            res[n][k] = {'rc': 'timeout'}
    b, f = res[n]['base'], res[n]['fixed']
    print(f"{n:42s} base rc={b.get('rc')} fixed rc={f.get('rc')}" + ('  SKIPPED-part' if f.get('skipped') else ''), flush=True)
Path(sys.argv[3]).write_text(json.dumps(res, indent=1))
bad = [n for n, v in res.items() if v['fixed'].get('rc') not in (0,) and v['base'].get('rc') != v['fixed'].get('rc')]
print('regressions (fixed fails where base differs):', bad)
