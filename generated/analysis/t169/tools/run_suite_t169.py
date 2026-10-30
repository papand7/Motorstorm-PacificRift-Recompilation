"""T169: every tools/test_*.py of the tree, one by one, with RSX and capture variables removed. Builds no exe.
usage: py -3 run_suite_t169.py <tree> <log dir>"""
import os, subprocess, sys, time
from pathlib import Path
T, L = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
L.mkdir(parents=True, exist_ok=True)
env = {k: v for k, v in os.environ.items() if not k.startswith(('RSX', 'GCM_', 'VP_', 'PS3_', 'RACE_', 'CELLMARK'))}
tot = {'PASS': 0, 'FAIL': 0, 'SKIP': 0, 'TIMEOUT': 0}
for s in sorted((T / 'tools').glob('test_*.py')):
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, str(s)], cwd=T, env=env, capture_output=True, text=True, errors='replace', timeout=420, stdin=subprocess.DEVNULL)
        out, rc = p.stdout + p.stderr, p.returncode
        v = 'FAIL' if rc else ('SKIP' if any(l.startswith('SKIP') for l in out.splitlines()) else 'PASS')
    except subprocess.TimeoutExpired as e:
        out, rc, v = str(e.stdout or ''), 'timeout', 'TIMEOUT'
    (L / (s.stem + '.log')).write_text(out, encoding='utf-8', errors='replace')
    tot[v] += 1
    print(f'{s.stem:44s} {v:7s} rc={rc} {time.time() - t0:6.1f}s', flush=True)
print('TOTAL', tot, flush=True)
