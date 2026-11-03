"""T162: correct_draw.sh frames, every arm against its <case>_cpu, by file name and SHA-256. Run from t162/gpuvtx/."""
import hashlib, pathlib, sys
d = pathlib.Path('runs/d')
bad = n = 0
h = lambda r: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (r / 'frames').iterdir()}
for ref in sorted(d.glob('*_cpu')):
    a = h(ref)
    c = ref.name[:-4]
    for o in sorted(d.glob(c + '_*')):
        if o == ref:
            continue
        n += 1
        b = h(o)
        ok = bool(a) and a == b
        bad += not ok
        print(o.name, len(b), len(a), 'identical' if ok else 'DIFFER')
print(f'compared {n}, differ {bad}')
sys.exit(1 if bad else 0)
