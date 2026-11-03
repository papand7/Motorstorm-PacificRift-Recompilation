"""T143: compare each correctness arm's RSXI snapshots with its "off" arm byte for byte (same file names,
same pixels), and count draws per RSXI frame.   py -3 cmp_snaps.py runs"""
import sys, pathlib, re, hashlib, json
d = pathlib.Path(sys.argv[1])
def snaps(run):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(run.glob('rsxi/**/*.bmp'))}
def draws(run):
    n = 0
    for p in run.glob('rsxi/**/events.jsonl'):
        n += sum(1 for l in p.open(encoding='utf-8', errors='replace') if '"e": "draw"' in l or '"e":"draw"' in l)
    return n
bad = 0
for off in sorted(d.glob('*_off')):
    base = off.name[:-4]; ref = snaps(off); rd = draws(off)
    for other in sorted(d.glob(base + '_*')):
        if other == off or other.name[len(base) + 1:] not in ('dedup', 'reuse', 'on', 'rerun_on', 'rerun_off'): continue
        s = snaps(other)
        diff = [k for k in ref if s.get(k) != ref[k]] + [k for k in s if k not in ref]
        ok = bool(ref) and not diff and draws(other) == rd
        bad += not ok
        print(f'{other.name:16s} vs {off.name:14s}: {len(s)}/{len(ref)} snapshots, draws {draws(other)}/{rd}: '
              + ('identical' if ok else f'DIFFERENT {diff[:4]}'))
print(f'cmp_snaps: {bad} arm(s) differ')
sys.exit(1 if bad else 0)
