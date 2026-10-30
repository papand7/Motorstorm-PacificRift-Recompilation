"""performance_next: compare RSXI pass snapshots of every <case>_<arm> run against <case>_ref, by path under rsxi/
(as t155/tools/cmp_snaps_t155.py). Exit 1 if any arm differs or has no snapshots.
  py -3 cmp_snaps_next.py <runs dir>"""
import hashlib, pathlib, sys
d = pathlib.Path(sys.argv[1])


def snaps(run):
    return {p.relative_to(run).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(run.glob('rsxi/**/*.bmp'))}


bad = 0
for ref in sorted(d.glob('*_ref')):
    case = ref.name[:-4]
    a = snaps(ref)
    for o in sorted(d.glob(case + '_*')):
        if o == ref:
            continue
        b = snaps(o)
        diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        ok = bool(a) and not diff
        bad += not ok
        print(f'{o.name:10s} vs {ref.name:9s}: {len(b)}/{len(a)} pass snapshots, '
              + ('identical' if ok else f'{len(diff)} differ: {[k for k in diff][:8]}'))
print(f'cmp_snaps_next: {bad} arm(s) differ')
sys.exit(1 if bad else 0)
