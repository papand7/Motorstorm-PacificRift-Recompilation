"""T155: [tex-rec] (RSX_TEXREC_STATS=1) per guest frame, split light / heavy by race-frame index.

  py -3 ana_texrec_t155.py <run_dir>     prints JSON

Race frame 0 = first [rsx-frame-perf] with draw_calls >= 200 (as t154/tools/phase_match_t154.py); light = race
frames 40..499, heavy = 600..end-1. [tex-rec] gframe= is the guest frame the pass belongs to (its lines report the
pass before them, tagged with that pass's own frame). Sums per guest frame, then mean / min / max over the segment,
with [rsx-frame-perf]'s tex ms and draw_calls of the same frames."""
import json, re, statistics as S, sys
from collections import defaultdict
from pathlib import Path

rd = Path(sys.argv[1])
NUM = re.compile(r'([a-z_]+)=([0-9.]+)')
TR = defaultdict(lambda: defaultdict(float))
npass = defaultdict(int)
fp = {}
for l in open(rd / 'stderr.log', encoding='utf-8', errors='replace'):
    if l.startswith('[tex-rec] gframe='):
        head, _, rest = l.partition(' | ')
        d = dict(NUM.findall(head))
        g = int(d['gframe'])
        npass[g] += 1
        for seg in l.split(' | ')[1:]:
            pre = 'us_' if seg.startswith('us ') else 'csum_' if seg.startswith('csum ') else ''
            for k, v in NUM.findall(seg):
                TR[g][pre + k] += float(v)
        for k in ('draws', 'lookups', 'bound'):
            TR[g][k] += float(d[k])
        TR[g]['bound_max'] = max(TR[g]['bound_max'], float(d['bound']))
    elif l.startswith('[rsx-frame-perf] gframe='):
        m = re.search(r'gframe=(\d+) .*?draw_calls=(\d+).*?\[tex ([0-9.]+) n=(\d+)', l)
        if m:
            fp[int(m[1])] = (int(m[2]), float(m[3]), int(m[4]))
g0 = min(g for g, v in fp.items() if v[0] >= 200)
end = max(fp) - g0
out = {'race_frame0_gframe': g0, 'race_frames': end}
KEYS = ['draws', 'lookups', 'bound_max', 'hit_bound', 'hit_csum', 'stale', 'shape', 'new', 'noslot', 'evict_other',
        'refetch_gf', 'recreate', 'creates', 'srv', 'csum_n', 'csum_src_mb', 'decode_mb', 'us_total', 'us_csum',
        'us_create', 'us_decode', 'us_copy', 'us_srv']
for seg, (a, b) in {'light': (40, 500), 'heavy': (600, end)}.items():
    gs = [g0 + i for i in range(a, b) if g0 + i in TR and g0 + i in fp]
    o = {'frames': len(gs), 'passes_per_frame': round(S.mean(npass[g] for g in gs), 2),
         'fpf_draws': round(S.mean(fp[g][0] for g in gs), 0), 'fpf_tex_ms': round(S.mean(fp[g][1] for g in gs), 2),
         'fpf_tex_n': round(S.mean(fp[g][2] for g in gs), 0)}
    for k in KEYS:
        v = [TR[g][k] for g in gs]
        o[k] = {'mean': round(S.mean(v), 2), 'min': round(min(v), 2), 'max': round(max(v), 2)}
    o['us_unattributed_mean'] = round(o['us_total']['mean'] - sum(o[k]['mean'] for k in
                                      ('us_csum', 'us_create', 'us_decode', 'us_copy', 'us_srv')), 1)
    o['us_per_lookup'] = round(o['us_total']['mean'] / o['lookups']['mean'], 3)
    out[seg] = o
print(json.dumps(out, indent=1))
