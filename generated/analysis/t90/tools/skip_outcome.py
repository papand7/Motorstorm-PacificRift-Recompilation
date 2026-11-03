"""T90: per run, heartbeat-ms of the press and of the first post-intro frontend open
(gui_c.bik or default.race); the difference says whether the intro was skipped
(seconds) or played out (~124 s). Also the largest heartbeat gap within 1 s of the press."""
import re
from pathlib import Path
RUNS = Path(__file__).resolve().parents[3] / 'runs'
hb = re.compile(r'\[rsx-hb\] ms=(\d+)')
for d in sorted(RUNS.iterdir()):
    f = d / 'stderr.log'
    if not f.is_file():
        continue
    ms, last, press, nxt, gaps = 0, None, None, None, []
    for l in f.open(errors='replace'):
        m = hb.search(l)
        if m:
            v = int(m.group(1))
            if last is not None:
                gaps.append((last, v))
            last = ms = v
        elif press is None and '[pad-trigger] press' in l:
            press = ms
        elif press is not None and nxt is None and '[fs] open' in l and ('gui_c.bik' in l or 'default.race' in l):
            nxt = ms
            break
    if press is None:
        continue
    g = max((b - a for a, b in gaps if b >= press and a <= press + 1200), default=0)
    dt = (nxt - press) / 1000 if nxt is not None else None
    verdict = 'SKIPPED' if dt is not None and dt < 30 else 'NOT SKIPPED'
    print(f'{d.name:45s} press_hb={press/1000:7.1f}s next_frontend_open={"-" if dt is None else f"+{dt:.1f}s":>8s} max_hb_gap_at_press={g:5d}ms {verdict}')
