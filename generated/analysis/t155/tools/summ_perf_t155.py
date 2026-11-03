"""T155: summarise runs/p (perf_texslots.sh). Per case and arm, over repeats: frames after the first two (warm-up),
mean per frame of [rsx-frame-perf] tex ms / record ms / rf ms / wall ms / tex n and of the [tex-rec] counters
(summed over the frame's passes); mean and range across repeats.   py -3 summ_perf_t155.py runs/p"""
import json, re, statistics as S, sys
from collections import defaultdict
from pathlib import Path
NUM = re.compile(r'([a-z_]+)=([0-9.]+)')
res = defaultdict(lambda: defaultdict(list))
for run in sorted(Path(sys.argv[1]).iterdir()):
    case, arm, rep = run.name.rsplit('_', 2)
    fp, tr = {}, defaultdict(lambda: defaultdict(float))
    for l in open(run / 'err.txt', encoding='utf-8', errors='replace'):
        if l.startswith('[rsx-frame-perf] gframe='):
            m = re.search(r'gframe=(\d+) .*?wall_ms=([0-9.]+).*?rf_ms=([0-9.]+).*?record_ms=([0-9.]+) \[tex ([0-9.]+) n=(\d+)', l)
            if m: fp[int(m[1])] = tuple(float(x) for x in m.groups()[1:])
        elif l.startswith('[tex-rec] gframe='):
            g = int(re.search(r'gframe=(\d+)', l)[1])
            for seg in l.split(' | ')[1:]:
                pre = 'us_' if seg.startswith('us ') else ''
                for k, v in NUM.findall(seg): tr[g][pre + k] += float(v)
    gs = [g for g in sorted(fp) if g > 2]
    if not gs: continue
    r = {k: S.mean(fp[g][i] for g in gs) for i, k in enumerate(('wall_ms', 'rf_ms', 'record_ms', 'tex_ms', 'tex_n'))}
    for k in ('noslot', 'new', 'evict_other', 'recreate', 'creates', 'srv', 'hit_csum', 'stale', 'decode_mb', 'us_create', 'us_decode'):
        r[k] = S.mean(tr[g][k] for g in gs if g in tr) if any(g in tr for g in gs) else 0.0
    r['us_per_bind'] = 1000.0 * r['tex_ms'] / r['tex_n'] if r['tex_n'] else 0.0
    for k, v in r.items(): res[(case, arm)][k].append(v)
out = {}
for (case, arm), d in sorted(res.items()):
    out[f'{case}/{arm}'] = {k: {'mean': round(S.mean(v), 3), 'min': round(min(v), 3), 'max': round(max(v), 3), 'n': len(v)}
                            for k, v in d.items()}
print(json.dumps(out, indent=1))
