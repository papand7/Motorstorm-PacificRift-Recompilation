MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""Run the bl4.cmd executables alternately; median ns/call per function and arm, state hashes."""
import os, re, statistics, subprocess, sys
from pathlib import Path
W = Path((MS_ROOT + r'\generated\analysis\t189\scratch\real\window_1'))
rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
R, K = (sys.argv[2] if len(sys.argv) > 2 else '3'), (sys.argv[3] if len(sys.argv) > 3 else '4')
env = dict(os.environ, PS3_VM_STORE_INLINE='1')
res, states = {}, {}
for _ in range(rounds):
    for arm in 'ABCD':
        out = ''.join(subprocess.run([str(W / arm / 'bench_rt.exe'), R, K, str(fi)], capture_output=True, text=True,
                                     env=env, timeout=1800).stdout for fi in (0, 2))   # fn 1 (func_000C9678) crashes the runtime on T152 inputs
        for m in re.finditer(r'^(func_[0-9A-F]{8}) \([^)]*\)\s+([\d.]+) ns/call.*state=([0-9A-F]+)', out, re.M):
            res.setdefault(m.group(1), {}).setdefault(arm, []).append(float(m.group(2)))
            states.setdefault(m.group(1), {}).setdefault(arm, set()).add(m.group(3))
        if arm == 'B' and _ == 0:
            print('\n'.join(l for l in out.splitlines() if 'gate' in l.lower() or l.startswith('#'))[:600])
print('| function | A ns/call | B | C | D | B/A | C/A | D/A | D/B | cv max | same state |')
print('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|')
for f, d in res.items():
    med = {a: statistics.median(d[a]) for a in d}
    cv = max(statistics.pstdev(d[a]) / statistics.mean(d[a]) for a in d)
    same = len(set().union(*states[f].values())) == 1
    print(f"| {f} | {med['A']:.0f} | {med['B']:.0f} | {med['C']:.0f} | {med['D']:.0f} | {med['A']/med['B']:.2f}x | "
          f"{med['A']/med['C']:.2f}x | {med['A']/med['D']:.2f}x | {med['B']/med['D']:.2f}x | {100*cv:.1f}% | {same} |")
