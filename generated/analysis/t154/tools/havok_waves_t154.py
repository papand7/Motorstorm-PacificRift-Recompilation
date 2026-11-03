"""T154: the Havok SPU task chain from the critical-path trace (kind 34 PS3_FT_SPU_TASK: who = host thread,
a = task image, start/end us; one short-lived host thread per task run).

  py -3 havok_waves_t154.py <cpath.txt> ...      prints JSON per trace

Tasks of one image that start within 4 ms of each other form a wave. Per image: tasks per wave, wave span
(first start -> last end), median task duration, start spread inside the wave; and per consecutive pair of
waves the handoff gap (last end of wave n -> first start of wave n+1). The chain = first start of the
first wave of a frame's sequence -> last end of its last wave; a sequence starts at each 145c1b7b wave."""
import json, statistics as S, sys
from collections import defaultdict


def med(v):
    return round(S.median(v), 3) if v else None


out = {}
for path in sys.argv[1:]:
    tasks = []
    for l in open(path, encoding='utf-8', errors='replace'):
        p = l.split()
        if p and p[0] == '34' and len(p) >= 6:
            tasks.append((float(p[4]) / 1000, float(p[5]) / 1000, p[2]))   # ms
    tasks.sort()
    waves = []
    for s, e, img in tasks:
        w = waves[-1] if waves else None
        if w and w['img'] == img and s - w['s0'] < 4.0:
            w['t'].append((s, e))
        else:
            waves.append({'img': img, 's0': s, 't': [(s, e)]})
    per = defaultdict(lambda: {'n': [], 'span': [], 'dur': [], 'spread': []})
    gaps = defaultdict(list)
    chains, seq = [], None
    for i, w in enumerate(waves):
        st = [s for s, _ in w['t']]; en = [e for _, e in w['t']]
        d = per[w['img']]
        d['n'].append(len(w['t'])); d['span'].append(max(en) - min(st))
        d['dur'].extend(e - s for s, e in w['t']); d['spread'].append(max(st) - min(st))
        if i:
            pv = waves[i - 1]
            gaps[pv['img'] + '>' + w['img']].append(min(st) - max(e for _, e in pv['t']))
        if w['img'] == '145c1b7b':
            if seq: chains.append(seq[1] - seq[0])
            seq = [min(st), max(en)]
        elif seq:
            seq[1] = max(seq[1], max(en))
    out[path] = {
        'tasks': len(tasks), 'waves': len(waves), 'chain_ms_median': med(chains), 'chains': len(chains),
        'images': {k: {'waves': len(v['n']), 'tasks_per_wave': med(v['n']), 'wave_span_ms': med(v['span']),
                       'task_ms': med(v['dur']), 'start_spread_ms': med(v['spread'])} for k, v in per.items()},
        'handoff_gap_ms': {k: {'n': len(v), 'median': med(v), 'p95': round(sorted(v)[int(len(v) * .95)], 3)}
                           for k, v in gaps.items() if len(v) > 20},
    }
print(json.dumps(out, indent=1))
