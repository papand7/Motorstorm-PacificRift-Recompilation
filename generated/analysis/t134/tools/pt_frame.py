"""T134: main-thread frame-phase split from an existing T122/T106 A/B run's [PT] trace (ab_fps.cfg sites).
  py -3 pt_frame.py <run_dir> [from_end_s=85] [to_end_s=15]
Window = [last PT t - from_end, last PT t - to_end] (the runner stops at race entry + 90 s, so the default
covers race entry + 5..75 s). Per fn and tid: calls, total ms, ms per guest frame (frames = 72E1E0 calls on tid 1).
Nested sites (736770 inside 50D868 etc.) are reported as-is, not subtracted."""
import re, sys, collections, statistics as S
from pathlib import Path
run = Path(sys.argv[1]); A = float(sys.argv[2]) if len(sys.argv) > 2 else 85; B = float(sys.argv[3]) if len(sys.argv) > 3 else 15
RX = re.compile(r'^\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=\w+ lr=\w+ fn=(\w+) .*?dur_us=(\d+)')
ev = []
for l in open(run / 'stderr.log', encoding='utf-8', errors='replace'):
    if l.startswith('[PT] t='):
        m = RX.match(l)
        if m and m[3] == 'exit':
            ev.append((int(m[1]), int(m[2]), m[4], int(m[5])))
tmax = max(e[0] for e in ev)
lo, hi = tmax - A * 1e6, tmax - B * 1e6
w = [e for e in ev if lo <= e[0] < hi]
frames = sum(1 for e in w if e[2] == '0072E1E0' and e[1] == 1)
span_s = (hi - lo) / 1e6
agg = collections.defaultdict(list)
for t, tid, fn, d in w:
    agg[(fn, tid)].append(d)
print(f'{run.name}: window {span_s:.0f} s, guest frames (72E1E0 tid1) {frames}, {frames/span_s:.2f}/s, {1000*span_s/max(frames,1):.1f} ms/frame')
for (fn, tid), v in sorted(agg.items(), key=lambda x: -sum(x[1])):
    print(f'  fn={fn} tid={tid:3d} calls={len(v):6d} total_ms={sum(v)/1e3:9.1f} ms/frame={sum(v)/1e3/max(frames,1):7.2f} '
          f'p50_us={S.median(v):8.0f} max_us={max(v)}')
