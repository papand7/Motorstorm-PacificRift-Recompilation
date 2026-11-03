"""T155: compare RSXI snapshots per pass (relative path under rsxi/, so per-pass files with the same name in different
frame folders are all compared; t153's cmp_snaps.py keyed by file name and compared only one of them).
  py -3 cmp_snaps_t155.py <runs dir>      each <case>_on / _rerun_on vs <case>_off; also reports dflt300 vs n300_off"""
import hashlib, pathlib, sys
d = pathlib.Path(sys.argv[1])
def snaps(run):
    return {p.relative_to(run).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(run.glob('rsxi/**/*.bmp'))}
bad = 0
pairs = [(o, off) for off in sorted(d.glob('*_off')) for o in sorted(d.glob(off.name[:-4] + '_*'))
         if o != off and o.name[len(off.name) - 3:] in ('on', 'rerun_on')]
if (d / 'dflt300').exists() and (d / 'n300_off').exists():
    pairs.append((d / 'dflt300', d / 'n300_off'))
for o, off in pairs:
    a, b = snaps(off), snaps(o)
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    ok = bool(a) and not diff
    expect_diff = o.name == 'dflt300'
    if not expect_diff: bad += not ok
    print(f'{o.name:14s} vs {off.name:10s}: {len(b)}/{len(a)} pass snapshots, '
          + ('identical' if ok else f'{len(diff)} differ: {[k.split("/")[2] for k in diff]}')
          + ('  (expected: 96 slots drop binds)' if expect_diff else ''))
print(f'cmp_snaps_t155: {bad} arm(s) differ')
sys.exit(1 if bad else 0)
