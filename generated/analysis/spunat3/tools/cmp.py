"""spunat3: alternating benchmark of several fnx executables (min-of-reps inside, median over rounds).

  python cmp.py <rounds> <label=exe> [<label=exe> ...] [-- bench args (default: 7 150 40)] [--env K=V ...]

Each round runs every executable once, in rotating order. Reports per executable and function the
median native and lifted time and their ratio (lifted / native = speedup of the natives against the
lifted baseline compiled into the SAME executable with the same flags and profile)."""
import json
import os
import re
import statistics
import subprocess
import sys

argv = sys.argv[1:]
rounds = int(argv.pop(0))
env = dict(os.environ, FX_CLEAN='1')
bargs = ['7', '150', '40']
exes = []
i = 0
while i < len(argv):
    if argv[i] == '--':
        bargs = argv[i + 1:]
        break
    if argv[i] == '--env':
        k, v = argv[i + 1].split('=', 1); env[k] = v; i += 2; continue
    lab, exe = argv[i].split('=', 1)
    exes.append((lab, exe)); i += 1
res = {lab: {} for lab, _ in exes}
for r in range(rounds):
    order = exes[r % len(exes):] + exes[:r % len(exes)]
    for lab, exe in order:
        o = subprocess.run([exe, 'bench'] + bargs, capture_output=True, text=True, env=env).stdout
        for m in re.finditer(r'^fn (\w+) .* native_ns (\d+) lifted_ns (\d+)', o, re.M):
            res[lab].setdefault(m.group(1), []).append((int(m.group(2)), int(m.group(3))))
        m = re.search(r'time native ([\d.]+) ms lifted ([\d.]+) ms', o)
        if m:
            res[lab].setdefault('TOTAL', []).append((float(m.group(1)) * 1e6, float(m.group(2)) * 1e6))
        if 'mismatches 0' not in o:
            print('WARNING: mismatches in', lab, exe)
out = {}
for lab, _ in exes:
    for fn, v in res[lab].items():
        n = statistics.median(x for x, _ in v); l = statistics.median(y for _, y in v)
        out.setdefault(lab, {})[fn] = dict(native_ns=n, lifted_ns=l, speedup=l / n if n else 0)
        print(f'{lab:14} {fn:6} native {n/1e3:10.1f} us  lifted {l/1e3:10.1f} us  speedup {l/n if n else 0:6.3f}')
print(json.dumps(out))
