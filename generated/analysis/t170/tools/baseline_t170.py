"""T170: per guest frame stage costs from [rsx-frame-perf] and [tex-rec] lines of an existing run. Read only.
usage: baseline_t170.py <run dir> [...]   Light: 1,500-3,000 records per guest frame; heavy: 5,000 or more."""
import re, sys, statistics as st, pathlib
NUM = re.compile(r'([a-z_]+)=(-?[0-9.]+)')
def parse(run):
    fr, tex = {}, {}
    for l in open(pathlib.Path(run) / 'stderr.log', errors='replace'):
        if l.startswith('[rsx-frame-perf] gframe='):
            d = {}
            for k, v in NUM.findall(l.replace('[tex ', 'tex_ms=').replace('| pso ', 'pso_ms=').replace('| cmd ', 'cmd_ms=').replace(' n=', ' tn=', 1)):
                d.setdefault(k, float(v))
            g = int(d['gframe'])
            fr.setdefault(g, []).append(d)
        elif l.startswith('[tex-rec] gframe='):
            d = {k: float(v) for k, v in NUM.findall(l)}
            tex.setdefault(int(d['gframe']), []).append(d)
    return fr, tex
KEYS = 'wall_ms records draw_calls verts upload_mb drain_ms draw_cb_ms expand_ms flush_ms miss_ms rf_ms record_ms tex_ms pso_ms cmd_ms submit_ms wait_ms present_ms other_ms'.split()
TK = 'draws lookups bound hit_bound hit_csum stale new evict_other recreate creates srv total csum create decode copy decode_mb src_mb'.split()
def agg(ps, keys): return {k: sum(p.get(k, 0.0) for p in ps) for k in keys}
def med(rows, k): return st.median(r[k] for r in rows)
def report(run):
    fr, tex = parse(run)
    rows = []
    for g in sorted(fr):
        r = agg(fr[g], KEYS); r['g'] = g; r['passes'] = len(fr[g])
        r.update({'t_' + k: v for k, v in agg(tex.get(g, []), TK).items()})
        rows.append(r)
    print('#', run, 'guest frames', len(rows))
    for name, lo, hi in (('light', 1500, 3000), ('heavy', 5000, 10 ** 9)):
        s = [r for r in rows if lo <= r['records'] < hi and r['wall_ms'] > 0]
        if not s:
            print(name, 'none'); continue
        print(f"{name}: n={len(s)} gframes {s[0]['g']}..{s[-1]['g']} passes med {med(s,'passes')} p90 wall {sorted(r['wall_ms'] for r in s)[int(len(s)*.9)]:.1f}")
        for k in KEYS + ['t_' + k for k in TK]:
            print(f'  {k:14s} {med(s,k):10.2f}  mean {st.mean(r[k] for r in s):10.2f}')
for a in sys.argv[1:]:
    report(a)
