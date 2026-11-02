"""Compare lifted trees: file hashes, then per-line differences of the files that differ.
usage: diff_lift_t173.py <tree A> <tree B> [max diff lines to print per file]"""
import hashlib, sys
from pathlib import Path

a, b = Path(sys.argv[1]), Path(sys.argv[2])
lim = int(sys.argv[3]) if len(sys.argv) > 3 else 6


def h(p):
    m = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 22), b''):
            m.update(c)
    return m.hexdigest()


fa = {p.name for p in a.iterdir() if p.suffix in ('.cpp', '.h')}
fb = {p.name for p in b.iterdir() if p.suffix in ('.cpp', '.h')}
print('only in A', sorted(fa - fb), '| only in B', sorted(fb - fa))
same, diff = 0, []
for n in sorted(fa & fb):
    if h(a / n) == h(b / n):
        same += 1
    else:
        diff.append(n)
print('identical files', same, '| different files', diff)
for n in diff:
    la, lb = (a / n).read_text('utf-8', 'replace').splitlines(), (b / n).read_text('utf-8', 'replace').splitlines()
    print(f'== {n}: {len(la)} vs {len(lb)} lines')
    k = 0
    for i, (x, y) in enumerate(zip(la, lb)):
        if x != y:
            k += 1
            if k <= lim:
                print(f'  line {i + 1}\n   A: {x[:260]}\n   B: {y[:260]}')
    print(f'  differing lines: {k}')
