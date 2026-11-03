"""T134: SPURS lane busy time ([spurs-busy], SPURS_BUSY_MS=1000) and per-thread syscall time
([sc-wait], PS3_SC_WAIT_MS=1000) of T106 A/B runs, over the race windows.
Both print once per second without a timestamp; the window is the last 75 one-second reports of
each series minus the final 5 (the runner stops at race entry + 90 s, so ~race entry +10..+80 s).
  py -3 lanes_scwait.py <run_dir> [...]"""
import re, sys, collections, json
from pathlib import Path

RB = re.compile(r'^\[spurs-busy\] spurs=(\w+) sn=(\d+) hosttid=(\d+) wid=(\d+) window_ms=(\d+) runs=(\d+) polled=(\d+) busy_ms=([\d.]+)')
RS = re.compile(r'^\[sc-wait\] window_ms=(\d+) tid=(\d+) total_ms=([\d.]+) (.*)$')
out = {}
for rd in sys.argv[1:]:
    run = Path(rd)
    busy = collections.defaultdict(list)     # (spurs, sn, wid) -> [(runs, polled, ms)]
    scw = collections.defaultdict(list)      # tid -> [{sc: (ms, calls)}]
    for l in open(run / 'stderr.log', encoding='utf-8', errors='replace'):
        m = RB.match(l)
        if m:
            busy[(m[1], int(m[2]), int(m[4]))].append((int(m[6]), int(m[7]), float(m[8])))
            continue
        m = RS.match(l)
        if m:
            d = {int(k): (float(a), int(b)) for k, a, b in re.findall(r'sc(\d+)=([\d.]+)ms/(\d+)', m[4])}
            scw[int(m[2])].append(d)
    # SPURS: per instance/wid, sum over lanes of the per-second mean
    per = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    lanes = collections.defaultdict(set)
    for (sp, sn, wid), v in busy.items():
        w = v[-80:-5] if len(v) > 85 else v
        per[(sp, wid)][0] += sum(x[2] for x in w) / len(w)
        per[(sp, wid)][1] += sum(x[0] for x in w) / len(w)
        per[(sp, wid)][2] += sum(x[1] for x in w) / len(w)
        if sum(x[2] for x in w) > 0:
            lanes[(sp, wid)].add(sn)
    r = {'spurs_busy_ms_per_s': {f'{sp} wid{wid}': {'busy_ms': round(a, 1), 'runs': round(b, 1), 'polled': round(c, 1),
                                                     'lanes_used': sorted(lanes[(sp, wid)])}
                                 for (sp, wid), (a, b, c) in sorted(per.items()) if a > 0.5},
         'lanes_busy_total': round(sum(a for a, _, _ in per.values()) / 1000.0, 3)}
    t1 = scw.get(1, [])
    w = t1[-80:-5] if len(t1) > 85 else t1
    agg = collections.defaultdict(lambda: [0.0, 0])
    for d in w:
        for k, (ms, n) in d.items():
            agg[k][0] += ms; agg[k][1] += n
    r['tid1_sc_ms_per_s'] = {f'sc{k}': {'ms': round(v[0] / len(w), 1), 'calls': round(v[1] / len(w), 1),
                                        'mean_us': round(1000 * v[0] / max(v[1], 1), 1)}
                             for k, v in sorted(agg.items(), key=lambda x: -x[1][0]) if v[0] / len(w) > 0.5} if w else {}
    out[run.name] = r
print(json.dumps(out, indent=1))
