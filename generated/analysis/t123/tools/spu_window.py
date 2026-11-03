"""T123: SPU-side numbers for one T106 A/B run's race window (no new tracing).
  py -3 -I spu_window.py <run_dir> [warmup_s=10] [window_s=70]
Window and clock as t106/ab/ab_analyze.py: race entry = PT clock at the first
[rsx-hb] with last_draws >= 200; non-PT lines take the clock of the last [PT].
CPU-time sums (busy_ms, sc-wait, thread CPU) are never added to wall time."""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

RX_PT = re.compile(r'^\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=([0-9A-F]+).*?fn=([0-9A-F]+)')
RX_HB = re.compile(r'^\[rsx-hb\] ms=(\d+) frames=(\d+) draw_frames=(\d+) last_draws=(\d+)')
RX_BUSY = re.compile(r'^\[spurs-busy\] spurs=0x([0-9A-F]+) sn=(\d+) hosttid=(\d+) wid=(\d+) window_ms=(\d+) '
                     r'runs=(\d+) polled=(\d+) busy_ms=([\d.]+)')
RX_SCW = re.compile(r'^\[sc-wait\] window_ms=(\d+) tid=(\d+) total_ms=([\d.]+)(.*)')
RX_SC = re.compile(r'sc(\d+)=([\d.]+)ms/(\d+)')
RX_IMG = re.compile(r'image=(\d+)')
RX_RFP = re.compile(r'^\[rsx-frame-perf\](.*)')

run = Path(sys.argv[1])
WARM = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
WIN = float(sys.argv[3]) if len(sys.argv) > 3 else 70.0
lines = (run / 'stderr.log').read_text(errors='replace').splitlines()

clock = 0
race_us = None
for l in lines:
    if l.startswith('[PT]'):
        m = RX_PT.match(l)
        if m: clock = int(m.group(1))
    elif race_us is None and l.startswith('[rsx-hb]'):
        m = RX_HB.match(l)
        if m and int(m.group(4)) >= 200: race_us = clock
assert race_us is not None, 'no race entry'
t0, t1 = race_us + WARM * 1e6, race_us + (WARM + WIN) * 1e6

frames = 0
busy = defaultdict(lambda: [0.0, 0, 0])          # (spurs, wid) -> busy_ms, runs, polled
lane = defaultdict(float)                         # hosttid -> busy_ms
scw = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))  # tid -> sc -> ms, calls
wl = Counter()
imgs = Counter()
clock = 0
for l in lines:
    if l.startswith('[PT]'):
        m = RX_PT.match(l)
        if not m: continue
        clock = int(m.group(1))
        if t0 <= clock < t1 and m.group(2) == '1' and m.group(3) == 'enter' and m.group(5) == '0072E1E0':
            frames += 1
        continue
    if not (t0 <= clock < t1): continue
    if l.startswith('[spurs-busy]'):
        m = RX_BUSY.match(l)
        if m:
            b = busy[(m.group(1), int(m.group(4)))]
            b[0] += float(m.group(8)); b[1] += int(m.group(6)); b[2] += int(m.group(7))
            lane[m.group(3)] += float(m.group(8))
    elif l.startswith('[sc-wait]'):
        m = RX_SCW.match(l)
        if m:
            for sc, ms, n in RX_SC.findall(m.group(4)):
                e = scw[int(m.group(2))][int(sc)]; e[0] += float(ms); e[1] += int(n)
    elif l.startswith('[spu_workload]'):
        k = ('dispatch' if 'dispatch HIT' in l else 'wait_signal' if 'WAIT_SIGNAL' in l else
             'signal' if ' signal task' in l else 'other')
        wl[k] += 1
        mi = RX_IMG.search(l)
        if mi: imgs[mi.group(1)] += 1
    elif l.startswith('[taskset]'):
        wl['taskset_built'] += 1
        mi = RX_IMG.search(l)
        if mi: imgs['ctx:' + mi.group(1)] += 1

out = {'run': run.name, 'frames': frames, 'fps': round(frames / WIN, 3)}
F = max(frames, 1)
out['spurs_busy_ms_per_frame'] = {'%s/wid%d' % k: {'busy': round(v[0] / F, 2), 'runs': round(v[1] / F, 1),
                                  'polled': round(v[2] / F, 1)} for k, v in sorted(busy.items())}
out['lane_busy_ms_per_frame'] = {k: round(v / F, 2) for k, v in sorted(lane.items())}
out['sc_wait_per_frame'] = {str(t): {('sc%d' % sc): {'ms': round(v[0] / F, 2), 'calls': round(v[1] / F, 1),
                                     'us_per_call': round(1000 * v[0] / v[1], 1) if v[1] else None}
                                     for sc, v in sorted(d.items()) if v[0] / F >= 0.05 or v[1] / F >= 1}
                            for t, d in sorted(scw.items())}
out['spu_workload_lines_per_frame'] = {k: round(v / F, 2) for k, v in wl.items()}
out['images_per_frame'] = {k: round(v / F, 2) for k, v in imgs.most_common(12)}

# Per-host-thread CPU from performance.json samples inside the window (by PT-free wall offset).
pj = run / 'performance.json'
if pj.exists():
    out['performance_json_keys'] = list(json.loads(pj.read_text()).keys())[:12]
print(json.dumps(out, indent=1))
