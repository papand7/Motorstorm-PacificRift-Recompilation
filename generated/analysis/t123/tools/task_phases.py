"""T123: where async SPU tasks start and end relative to the frame phases (order only;
no new tracing). Each [spu_workload] dispatch / HOST_RUN_ENDED / [taskset] line is
placed in the phase of the frame-thread PT event that precedes it in stderr.log.
  py -3 -I task_phases.py <run_dir> [warmup_s=10] [window_s=70]
Phases (t104 frame_phases): ref = 72E1E0 enter..exit, pre = ref exit..first 50D868,
emit = first..last 50D868, tail = after the last 50D868 (gap + spin)."""
import re, sys
from collections import Counter, defaultdict
from pathlib import Path

RX_PT = re.compile(r'^\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=([0-9A-F]+).*?fn=([0-9A-F]+)')
RX_HB = re.compile(r'^\[rsx-hb\] ms=(\d+) frames=(\d+) draw_frames=(\d+) last_draws=(\d+)')
RX_IMG = re.compile(r'image=(\d+)')

run = Path(sys.argv[1])
WARM = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
WIN = float(sys.argv[3]) if len(sys.argv) > 3 else 70.0
lines = (run / 'stderr.log').read_text(errors='replace').splitlines()

clock = 0; race = None
for l in lines:
    if l.startswith('[PT]'):
        m = RX_PT.match(l)
        if m: clock = int(m.group(1))
    elif race is None and l.startswith('[rsx-hb]'):
        m = RX_HB.match(l)
        if m and int(m.group(4)) >= 200: race = clock
t0, t1 = race + WARM * 1e6, race + (WARM + WIN) * 1e6

phase = None; clock = 0; frames = 0
cnt = defaultdict(Counter)          # kind -> phase -> n
last_before_pb = Counter()          # what the last SPU line before the first 50D868 was
last_spu = None
for l in lines:
    if l.startswith('[PT]'):
        m = RX_PT.match(l)
        if not m or m.group(2) != '1': continue
        clock = int(m.group(1)); fn = m.group(5); ev = m.group(3)
        if not (t0 <= clock < t1): continue
        if fn == '0072E1E0':
            if ev == 'enter': phase = 'ref'; frames += 1
            else: phase = 'pre'; last_spu = None
        elif fn == '0050D868' and ev == 'enter':
            if phase == 'pre': last_before_pb[last_spu or 'none'] += 1
            phase = 'emit'
        elif fn == '0050C818' and ev == 'enter':
            phase = 'tail'
        continue
    if phase is None or not (t0 <= clock < t1): continue
    k = None
    if 'dispatch HIT (async)' in l: k = 'dispatch'
    elif 'HOST_RUN_ENDED' in l: k = 'end'
    elif l.startswith('[taskset] start task'): k = 'chain_start'
    if not k: continue
    mi = RX_IMG.search(l)
    img = mi.group(1) if mi else '?'
    cnt['%s img=%s' % (k, img)][phase] += 1
    if phase == 'pre': last_spu = '%s img=%s' % (k, img)

F = max(frames, 1)
print('run', run.name, 'frames', frames)
for k in sorted(cnt):
    print('  %-28s' % k, '  '.join('%s=%.2f' % (p, cnt[k][p] / F) for p in ('ref', 'pre', 'emit', 'tail')))
print('  last SPU-task line before the first ExecutePushBuffer (frames):')
for k, n in last_before_pb.most_common(): print('    %-28s %d' % (k, n))
