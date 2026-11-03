"""T70C: compiler warnings that fall on lines the T70C changes added (git diff <base> of the
ps3recomp-t70 worktree), from compile_tus.py's per-TU logs. Usage: py -3 -I t70c_new_warnings.py <objs dir> <base rev>"""
import re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
W = ROOT / 'ps3recomp-t70'
added = {}
d = subprocess.run(['git', '-C', str(W), 'diff', '-U0', sys.argv[2]], capture_output=True, text=True).stdout
cur = None
for l in d.splitlines():
    if l.startswith('+++ b/'):
        cur = Path(l[6:]).name; added.setdefault(cur, set())
    m = re.match(r'@@ -\S+ \+(\d+)(?:,(\d+))? @@', l)
    if m and cur:
        a, n = int(m.group(1)), int(m.group(2) or 1)
        added[cur] |= set(range(a, a + n))
hits = set()
for log in Path(sys.argv[1]).glob('*.log'):
    for m in re.finditer(r'([\w.]+)\((\d+),\d+\): warning: (.*?)\[(-W[^\]]+)\]', log.read_text(errors='replace')):
        f, ln = m.group(1), int(m.group(2))
        if ln in added.get(f, ()):
            hits.add((f, ln, m.group(4), m.group(3).strip()[:120]))
print(f'changed files: {sorted(added)}; added lines: {sum(map(len, added.values()))}')
for h in sorted(hits):
    print('  ', *h)
print(f'warnings on added lines: {len(hits)} distinct')
