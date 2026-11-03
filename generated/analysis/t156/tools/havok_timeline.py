"""T156: Havok wave timeline from the critical-path trace (kind 34 task runs; kinds 38/39 when present).

  py -3 havok_timeline.py <cpath.txt> ...        prints JSON per trace

Waves = runs of one image starting within 4 ms (as T154's havok_waves_t154.py). Per wave image: medians
of the wave span (first start -> last end), the longest task, the sum of task times, the ideal span if
that work were shared by 5 lanes from the first start (sum / 5), the start spacing between consecutive
tasks, the start spread, and the end spread (last end - first end: ~0 means the tasks drain a shared
queue and finish together). Per chain (wave 1 start -> wave 3 end): the median, and how much of it the
PPU's serial task creation (wave-3 start spread) and wave-1 start spread take.
With T156 kinds present: dispatch cost on the caller (38), dispatch -> pick-up (34.b), pick-up -> entry
(39.b), entry run (39), and exit bookkeeping (34.t1 - 39.t1), per wave image."""
import json
import statistics as S
import sys
from collections import defaultdict

IMG = {'145c1b7b': 'w1 solver', '1d51c6ce': 'w2 collide', '1266e45a': 'w3 raycast', '18345147': 'w4 animation'}


def med(v):
    return round(S.median(v), 3) if v else None


out = {}
for path in sys.argv[1:]:
    tasks, sub, run = [], defaultdict(list), {}
    for l in open(path, encoding='utf-8', errors='replace'):
        p = l.split()
        if not p or not p[0].isdigit() or len(p) < 6:
            continue
        k = int(p[0])
        if k == 34:
            tasks.append((float(p[4]) / 1000, float(p[5]) / 1000, p[2], int(p[3], 16), p[1]))
        elif k == 38:
            sub[p[2]].append(float(p[5]) - float(p[4]))
        elif k == 39:
            run[(p[1], p[2], round(float(p[4]) / 1000, 3))] = (float(p[4]) / 1000, float(p[5]) / 1000, int(p[3], 16))
    tasks.sort()
    waves = []
    for s, e, img, lat, who in tasks:
        w = waves[-1] if waves else None
        if w and w['img'] == img and s - w['s0'] < 4.0:
            w['t'].append((s, e, lat, who))
        else:
            waves.append({'img': img, 's0': s, 't': [(s, e, lat, who)]})
    per = defaultdict(lambda: defaultdict(list))
    for w in waves:
        if len(w['t']) < 2:
            continue
        st = sorted(x[0] for x in w['t']); en = sorted(x[1] for x in w['t'])
        d = [x[1] - x[0] for x in w['t']]
        q = per[w['img']]
        q['span'].append(en[-1] - st[0]); q['longest'].append(max(d)); q['sum'].append(sum(d))
        q['ideal5'].append(sum(d) / 5); q['spread'].append(st[-1] - st[0]); q['endspread'].append(en[-1] - en[0])
        q['spacing'].extend(b - a for a, b in zip(st, st[1:]))
        q['lat_us'].extend(x[2] for x in w['t'] if x[2])
    chains, seq = [], None
    for w in waves:
        st = min(x[0] for x in w['t']); en = max(x[1] for x in w['t'])
        if w['img'] == '145c1b7b':
            seq = {'s': st, 'e': en, 'w1spread': max(x[0] for x in w['t']) - st}
        elif seq and w['img'] == '1d51c6ce':
            seq['e'] = en
        elif seq and w['img'] == '1266e45a':
            seq['e'] = en; seq['w3spread'] = max(x[0] for x in w['t']) - st
            chains.append(seq); seq = None
    o = {'tasks': len(tasks), 'chains': len(chains),
         'chain_ms': med([c['e'] - c['s'] for c in chains]),
         'chain_w1_start_spread_ms': med([c['w1spread'] for c in chains]),
         'chain_w3_start_spread_ms': med([c['w3spread'] for c in chains]),
         'waves': {}}
    for img, q in per.items():
        o['waves'][IMG.get(img, img)] = {k: med(v) for k, v in q.items()} | {'n': len(q['span'])}
    if sub or run:
        o['t156'] = {'dispatch_us_by_image': {IMG.get(k, k): med(v) for k, v in sub.items()}}
        pro = defaultdict(list); body = defaultdict(list)
        for (who, img, _), (s, e, b) in run.items():
            pro[img].append(b); body[img].append(e - s)
        o['t156']['prologue_us'] = {IMG.get(k, k): med(v) for k, v in pro.items()}
        o['t156']['entry_ms'] = {IMG.get(k, k): med(v) for k, v in body.items()}
    out[path] = o
print(json.dumps(out, indent=1))
