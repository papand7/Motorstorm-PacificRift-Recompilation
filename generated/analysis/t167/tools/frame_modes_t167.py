#!/usr/bin/env python3
"""T167: normal against slow frames in existing [rsx-frame-perf] logs, and when each run enters and leaves the 84 ms mode.

  py -3 frame_modes_t167.py <run dir> [...]

Frames are few-draw (< 100 draw calls) or many-draw (>= 1000), slow if wait_ms > 50. A mode segment needs 30 frames in a row on a
median of the last 30 to count, so single long frames do not switch it. Host time comes from the last [rsx-hb] line."""
import re, statistics as S, sys
from pathlib import Path

for rd in sys.argv[1:]:
    fr, hb = [], 0.0
    for l in open(Path(rd) / 'stderr.log', errors='replace'):
        m = re.match(r'\[rsx-hb\] ms=(\d+)', l)
        if m:
            hb = int(m.group(1)) / 1000
        elif l.startswith('[rsx-frame-perf] gframe='):
            g = lambda n: float(re.search(r'\b' + n + r'=([\d.]+)', l).group(1))
            if ' wait_ms=' in l:
                fr.append((hb, int(g('gframe')), g('draw_calls'), g('wall_ms'), g('wait_ms'), g('present_ms'), g('record_ms'), g('other_ms')))
    print(Path(rd).name, 'frames', len(fr))
    for nm, sel in (('few', lambda f: f[2] < 100), ('many', lambda f: f[2] >= 1000)):
        for st, w in (('normal', lambda f: f[4] <= 50), ('slow', lambda f: f[4] > 50)):
            x = [f for f in fr if sel(f) and w(f)]
            if x:
                print(f'  {nm:4s} {st:6s} n={len(x):5d} draws={S.median(f[2] for f in x):6.0f} wall={S.median(f[3] for f in x):6.1f} '
                      f'wait={S.median(f[4] for f in x):6.1f} present={S.median(f[5] for f in x):5.2f} '
                      f'record={S.median(f[6] for f in x):6.1f} other={S.median(f[7] for f in x):6.1f}')
    mode, seg = None, []
    for i in range(30, len(fr), 10):
        m = S.median(f[4] for f in fr[i - 30:i]) > 50
        if m != mode:
            seg.append(f"{'slow' if m else 'normal'} from {fr[i - 30][0]:.0f}s/gframe {fr[i - 30][1]}")
            mode = m
    print('  modes:', '; '.join(seg))
