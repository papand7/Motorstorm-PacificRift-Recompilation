"""T158: run the function-level differential test over images x seeds; print one summary row each.

  py -3 hvk_diff_all.py <hvkbuild dir> <cases per function> <seeds e.g. 1,2,3> [images]
Exit 1 if any run reports a mismatch, a halt difference, a step-count difference or fails."""
import re
import subprocess
import sys
from pathlib import Path

B, CASES, SEEDS = Path(sys.argv[1]), sys.argv[2], sys.argv[3].split(',')
IMGS = sys.argv[4].split(',') if len(sys.argv) > 4 else ['solver', 'collide', 'raycast', 'anim']
bad = 0
for img in IMGS:
    for seed in SEEDS:
        r = subprocess.run([str(B / img / f'hvkdiff_{img}.exe'), 'diff', seed, CASES], capture_output=True,
                           text=True, timeout=3600)
        o = r.stdout
        g = lambda pat: (re.search(pat, o) or [None, '?'])[1]
        acc = re.search(r'cases tried (\d+) accepted (\d+) \(functions with accepted cases (\d+) of (\d+)\)', o)
        hops = re.search(r'drain hops C0 (\d+) C1 (\d+) \(([\d.]+)% removed\); step counts C0 (\d+) C1 (\d+)', o)
        ins = g(r'executed SPU instructions (\d+)')
        mm = g(r'mismatches (\d+)')
        ref = g(r'refused:(.*)')
        print(f'{img:8s} seed {seed}: rc={r.returncode} tried={acc and acc[1]} accepted={acc and acc[2]} '
              f'functions={acc and acc[3]}/{acc and acc[4]} spu_insns={ins} hops C0={hops and hops[1]} '
              f'C1={hops and hops[2]} ({hops and hops[3]}% removed) steps_equal={hops and hops[4] == hops[5]} '
              f'mismatches={mm} | refused{ref}')
        for line in o.splitlines():
            if line.startswith(('MISMATCH', 'STEPS', 'HALT')):
                print('   ', line)
        bad |= r.returncode != 0 or mm != '0'
print('RESULT', 'FAIL' if bad else 'PASS')
sys.exit(1 if bad else 0)
