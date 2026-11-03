#!/usr/bin/env python3
"""T161: offline test of bench_t161.py on a synthetic log (py -3 test_bench_t161.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_t161 import parse, windows

fails = 0
def check(c, msg):
    global fails
    if not c:
        fails += 1
        print('FAIL:', msg)

def fp(g, p, wall, draws, comp=0.0):
    return (f'[rsx-frame-perf] gframe={g} pass={p} wall_ms={wall} | passes=1 early=0 records=0 draw_calls={draws} '
            f'verts=0 upload_mb=0.0 | drain_ms=2.0 draw_cb_ms=0.0 expand_ms=0.0 flush_ms=0.0 vs=0/0 miss_ms=0.0 | '
            f'rf_ms=1.0 (in_drain 0.0) record_ms=1.0 [tex 0.0 n=0 | pso 0.0 n=0 miss=0 miss_ms={comp} | cmd 1.0] '
            f'submit_ms=0.1 wait_ms=0.0 present_ms=0.1 | other_ms=5.0\n')

L = ['[rsx-frame-perf] on: first 12 guest frames, then every 1, at most 100000 lines\n']
L += [fp(g, 1, 33.3, 10) for g in range(1, 50)]                     # loading screen
g = 50
for rf in range(0, 700):                                           # race: light 40 ms, heavy 4 passes x 20 ms
    if rf < 600:
        L.append(fp(g, 1, 40.0, 2000, comp=100.0 if rf < 40 else 0.0))
    else:
        for p in range(1, 5):
            L.append(fp(g, p, 20.0, 1700))
    g += 1
L.append(fp(g, 1, 1.0, 2000))                                       # partial last line, dropped
L += ['[rsx-hb] ms=60000 frames=1 draw_frames=1\n',
      '[hle-wait] window_ms=1000 tid=1 total_ms=900.00 nid2A6D9D51=600.00ms/500 nid4D5FF8E2=300.00ms/30\n',
      '[sc-wait] window_ms=1000 tid=1 total_ms=1.00 sc141=1.00ms/4\n',
      '[rsx-hb] ms=200000 frames=1 draw_frames=1\n',
      '[hle-wait] window_ms=1000 tid=1 total_ms=50.00 nid2A6D9D51=50.00ms/40\n']

frames, waits = parse(L)
w = windows(frames, (600, 700))
check(w['race_frames'] == 700, f"700 race guest frames (got {w['race_frames']})")
check(w['light']['complete'] and w['light']['fps'] == 25.0, f"light 460 frames at 25 fps ({w['light']})")
check(w['heavy']['complete'] and w['heavy']['fps'] == 12.5 and w['heavy']['passes_med'] == 4,
      f"heavy: 4 passes x 20 ms per guest frame = 12.5 fps ({w['heavy']})")
check(w['heavy']['draw_calls_med'] == 6800, 'heavy draw calls summed over passes')
check(w['warmup']['compile_ms'] == 4000.0 and w['light']['compile_ms'] == 0.0, 'compiles land in warmup only')
w2 = windows(frames, (600, 900))
check(not w2['heavy']['complete'] and w2['heavy']['frames'] == 100, 'heavy window incomplete when the run stops early')
check(waits[(1, 'hle:sys_lwcond_wait')] == [650.0, 540] and waits[(1, 'hle:cellFsRead')] == [300.0, 30], 'hle-wait parsed')
check(waits[(1, 'sc141')] == [1.0, 4], 'sc-wait parsed')
_, wspan = parse(L, (50.0, 100.0))
check(wspan[(1, 'hle:sys_lwcond_wait')] == [600.0, 500], 'wait span by [rsx-hb] host clock')

print(f'test_bench_t161: {fails} failure(s)')
sys.exit(1 if fails else 0)
