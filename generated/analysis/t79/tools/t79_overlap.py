#!/usr/bin/env python3
"""T79D: peak simultaneous lanes per WWS workload from a run's ftrace (read-only).

  py -3 -I t79_overlap.py <run dir>

Kind 26 (completed) and 30 (LOST) spans: r[3] >> 24 = wid, r[4]/r[5] = start/end us. r[1] is ctx->spu_id,
which is 0 on every SPURS lane, so lanes are not named; but spu_jobspan keeps one open span per host thread
(lane), so the number of spans open at one instant is the number of lanes busy then. Reports, per wid and
per span class (job / pm / all), that peak and the time share at each level. Uses ab_report.py's loader and T70F classes."""
import collections, importlib.util, sys
from pathlib import Path

AB = Path(__file__).resolve().parents[2] / 't70' / 'ab' / 'ab_report.py'
spec = importlib.util.spec_from_file_location('ab_report', AB)
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)


def overlap(spans):
    ev = []
    for lane, s, e in spans:
        ev.append((s, 1, lane))
        ev.append((e, -1, lane))
    ev.sort(key=lambda x: (x[0], x[1]))
    lvl, peak, t_prev, at = 0, 0, None, collections.Counter()
    for t, d, lane in ev:
        if t_prev is not None:
            at[lvl] += t - t_prev
        lvl += d
        peak = max(peak, lvl)
        t_prev = t
    return peak, at


def main(rd):
    rd = Path(rd)
    ft, hdr, _ = ab.load_ftrace(rd / 'ftrace.txt')
    m = ab.RX_HDR.search(hdr)
    lo, hi = float(m.group(1)), float(m.group(2))
    by = collections.defaultdict(list)
    lanes = collections.defaultdict(set)
    for r in ft:
        if r[0] in (26, 30) and lo <= r[4] < hi:
            w, c = r[3] >> 24, ab.span_class(r[2])
            by[(w, c)].append((r[1], r[4], r[5]))
            by[(w, 'all')].append((r[1], r[4], r[5]))
            lanes[w].add(r[1])
    print(f'run {rd.name} window {lo/1e6:.1f}-{hi/1e6:.1f} s')
    for (w, c) in sorted(by):
        peak, at = overlap(by[(w, c)])
        tot = sum(at.values()) or 1
        share = ' '.join(f'{k}:{v / tot * 100:.1f}%' for k, v in sorted(at.items()))
        print(f'wid {w} class {c:4s} spans {len(by[(w, c)]):6d} lanes_seen {sorted(lanes[w])} peak_simultaneous {peak}  time_at_level {share}')
    # cross-workload: distinct lanes busy with any job span at once
    allsp = [s for (w, c), v in by.items() if c == 'all' for s in v]
    peak, at = overlap(allsp)
    tot = sum(at.values()) or 1
    print(f'any wid: peak simultaneous lanes {peak}  time_at_level ' +
          ' '.join(f'{k}:{v / tot * 100:.1f}%' for k, v in sorted(at.items())))


if __name__ == '__main__':
    main(sys.argv[1])
