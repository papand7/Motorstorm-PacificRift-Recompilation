"""Run bench_march.cmd's two executables alternately (A = baseline x86-64, V = -march=x86-64-v3
-ffp-contract=off); median ns/call per function and arm, the final guest state hash of each.
Store policy from the environment: PS3_VM_STORE_INLINE unset = the game default (out of line).

usage: py -3 run_bench_march.py [rounds=7] [reps=3] [iters=4] [--inline]"""
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[1] / 'scratch' / 'march'
args = [a for a in sys.argv[1:] if not a.startswith('--')]
rounds = int(args[0]) if args else 7
R, K = (args[1] if len(args) > 1 else '3'), (args[2] if len(args) > 2 else '4')
env = dict(os.environ)
env.pop('PS3_VM_STORE_INLINE', None)
if '--inline' in sys.argv:
    env['PS3_VM_STORE_INLINE'] = '1'
res, states = {}, {}
for _ in range(rounds):
    for arm in 'AV':
        # fn 1 (func_000C9678) crashes the real runtime on T152's inputs (T189)
        out = ''.join(subprocess.run([str(W / arm / 'bench_rt.exe'), R, K, str(fi)], capture_output=True,
                                     text=True, env=env, timeout=1800).stdout for fi in (0, 2))
        for m in re.finditer(r'^(func_[0-9A-F]{8}) \([^)]*\)\s+([\d.]+) ns/call.*state=([0-9A-F]+)', out, re.M):
            res.setdefault(m.group(1), {}).setdefault(arm, []).append(float(m.group(2)))
            states.setdefault(m.group(1), {}).setdefault(arm, set()).add(m.group(3))
print('stores', 'inline' if '--inline' in sys.argv else 'out of line', '| rounds', rounds)
print('| function | A ns/call | V ns/call | A/V (median) | A/V (min) | cv max | same state |')
print('|---|---:|---:|---:|---:|---:|---|')
for f, d in res.items():
    med = {a: statistics.median(d[a]) for a in d}
    cv = max(statistics.pstdev(d[a]) / statistics.mean(d[a]) for a in d)
    same = len(set().union(*states[f].values())) == 1
    mn = {a: min(d[a]) for a in d}
    print(f"| {f} | {med['A']:.0f} | {med['V']:.0f} | {med['A'] / med['V']:.2f}x | {mn['A'] / mn['V']:.2f}x | "
          f"{100 * cv:.1f}% | {same} |")
