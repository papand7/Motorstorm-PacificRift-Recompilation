#!/usr/bin/env python3
"""T79E: C1 vs C5 from ab_report.py texts + raw ftrace (read-only).

  py -3 -I t79e_compare.py <C1 report> <C1 run dir> <C5 report> <C5 run dir>

Per module (report rows; runs include PM-attributed spuconstraints, = kind 28 module records): runs/frame,
median, ms/frame. Lanes cannot be named (span field 1 = ctx->spu_id = 0 on every SPURS lane), so 'dispatch
gaps' here are the idle intervals of the union of open spans (job + pm class, kind 26/30) per wid and over all
wids, inside the window: union busy ms/frame, idle-gap count, median and p95. wid 3 (LibMP3) runs per
SPURS_BUSY second from stderr, as an audio progress check."""
import collections, importlib.util, re, statistics, sys
from pathlib import Path

AB = Path(__file__).resolve().parents[2] / 't70' / 'ab' / 'ab_report.py'
spec = importlib.util.spec_from_file_location('ab_report', AB)
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)
ROW = re.compile(r'^\s*\|\s+(\d)\s+(.+?)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+[\d.]+%')


def report(p):
    t = Path(p).read_text(errors='replace')
    g = lambda k: float(re.search(rf'^\s*{k}: ([\d.]+)', t, re.M).group(1))
    mods = {}
    for m in (ROW.match(l) for l in t.splitlines()):
        if m and not m.group(2).startswith('job id'):
            mods[m.group(2)] = (int(m.group(3)), float(m.group(4)), float(m.group(5)))
    return dict(fps=g('fps'), frames=g('frames'), win=g('window_len_s'), wait=g('ppu_main_wait_ms_per_frame'),
                havok=g('havok_steps_per_frame'), race=g('race_entry_s'),
                fm=eval(re.search(r"frame_ms: (\{.*\})", t).group(1)), mods=mods)


def union(spans):
    spans.sort()
    busy, gaps, cur = 0.0, [], None
    for s, e in spans:
        if cur is None:
            cur = [s, e]
        elif s > cur[1]:
            busy += cur[1] - cur[0]
            gaps.append(s - cur[1])
            cur = [s, e]
        else:
            cur[1] = max(cur[1], e)
    if cur:
        busy += cur[1] - cur[0]
    return busy, gaps


def spans(rd):
    ft, hdr, _ = ab.load_ftrace(Path(rd) / 'ftrace.txt')
    m = ab.RX_HDR.search(hdr)
    lo, hi = float(m.group(1)), float(m.group(2))
    by = collections.defaultdict(list)
    for r in ft:
        if r[0] in (26, 30) and lo <= r[4] < hi:
            by[r[3] >> 24].append((r[4], min(r[5], hi)))
            by['any'].append((r[4], min(r[5], hi)))
    return by


def wid3(rd):
    per = collections.Counter()
    for ln in open(Path(rd) / 'stderr.log', errors='replace'):
        m = re.search(r'\[spurs-busy\].* wid=3 .*runs=(\d+).* pass=(\d+)', ln)
        if m:
            per[int(m.group(2))] += int(m.group(1))
    v = [per[k] for k in sorted(per)]
    return v


def pct(a, b):
    return f'{(b - a) / a * 100:+.1f} %' if a else 'n/a'


A, B = report(sys.argv[1]), report(sys.argv[3])
print('| Metric | C1 | C5 | change | % |\n|---|---|---|---|---|')
for k, lab in (('race', 'Race entry s'), ('win', 'Window s'), ('frames', 'Frames'), ('fps', 'Race fps'),
               ('wait', 'PPU main wait ms/frame'), ('havok', 'Havok steps/frame')):
    print(f'| {lab} | {A[k]:.2f} | {B[k]:.2f} | {B[k] - A[k]:+.2f} | {pct(A[k], B[k])} |')
for k in ('mean', 'p50', 'p95', 'p99'):
    print(f'| Frame ms {k} | {A["fm"][k]:.1f} | {B["fm"][k]:.1f} | {B["fm"][k] - A["fm"][k]:+.1f} | {pct(A["fm"][k], B["fm"][k])} |')
print('\n| Module | C1 runs/frame | C5 runs/frame | C1 med ms | C5 med ms | med ratio C5/C1 | C1 lane-ms/frame | C5 lane-ms/frame |')
print('|---|---|---|---|---|---|---|---|')
ta = tb = 0.0
for n in sorted(set(A['mods']) | set(B['mods']), key=lambda n: -A['mods'].get(n, (0, 0))[1]):
    a, b = A['mods'].get(n, (0, 0, 0)), B['mods'].get(n, (0, 0, 0))
    fa, fb = a[1] / A['frames'], b[1] / B['frames']
    ta += fa; tb += fb
    r = f'{b[2] / a[2]:.2f}' if a[2] else 'n/a'
    print(f'| {n} | {a[0] / A["frames"]:.2f} | {b[0] / B["frames"]:.2f} | {a[2]:.3f} | {b[2]:.3f} | {r} | {fa:.1f} | {fb:.1f} |')
print(f'| **all** | | | | | | {ta:.1f} | {tb:.1f} ({pct(ta, tb)}) |')
print('\nUnion of open spans (job+pm), per wid: busy ms/frame (wall), idle gaps n / median us / p95 us')
SA, SB = spans(sys.argv[2]), spans(sys.argv[4])
for w in (0, 1, 2, 'any'):
    out = []
    for lab, S, R in (('C1', SA, A), ('C5', SB, B)):
        busy, g = union(S.get(w, []))
        g.sort()
        out.append(f'{lab} {busy / 1e3 / R["frames"]:.1f} ms/frame, gaps {len(g)} / '
                   f'{statistics.median(g) if g else 0:.1f} / {g[int(0.95 * (len(g) - 1))] if g else 0:.1f}')
    print(f'wid {w}: ' + ' | '.join(out))
for lab, rd in (('C1', sys.argv[2]), ('C5', sys.argv[4])):
    v = wid3(rd)
    print(f'{lab} wid 3 (LibMP3) runs per SPURS_BUSY second: n={len(v)} zero-seconds={sum(1 for x in v if x == 0)} '
          f'min={min(v)} median={statistics.median(v)} last10={v[-10:]}')
