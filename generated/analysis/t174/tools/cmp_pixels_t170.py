"""T170: per-arm frame hashes against arm base. Prints identical frames and the first difference."""
import sys, pathlib
root = pathlib.Path(sys.argv[1])
def load(a):
    p = root / a / 'sha.txt'
    return dict((l.split()[1], l.split()[0]) for l in p.read_text().splitlines()) if p.exists() else {}
base = load('base')
print('base frames', len(base), 'unique', len(set(base.values())))
bad = 0
for d in sorted(x.name for x in root.iterdir() if x.is_dir()):
    if d == 'base': continue
    cur = load(d)
    same = sum(1 for k in base if cur.get(k) == base[k])
    diff = [k for k in base if cur.get(k) != base[k]]
    bad += bool(diff)
    print(f'{d}: {same}/{len(base)} identical', ('first difference ' + diff[0]) if diff else '')
print('pixels_t170:', bad, 'arm(s) differ')
