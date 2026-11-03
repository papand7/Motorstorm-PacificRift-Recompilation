"""T169: one run's stderr: frame-time percentiles (race frames, light < 700 draw calls, heavy >= 700), wait_ms mode, draw counts,
c33.x timeline, PSO and device failures. usage: py -3 runtime_summary_t169.py <run dir> [<run dir>...]"""
import re, statistics as st, sys
from pathlib import Path

RX = re.compile(r'\[rsx-frame-perf\] gframe=(\d+) .*?wall_ms=([\d.]+) .*?records=(\d+) draw_calls=(\d+).*?record_ms=([\d.]+).*?wait_ms=([\d.]+)')
RXC = re.compile(r'\[vpc-watch\].*|\[VPC.*')
BAD = re.compile(r'pso_fail|PSO creation FAIL|DEVICE_REMOVED|DeviceRemoved|device removed|GetDeviceRemovedReason|E_INVALIDARG|Gc ERROR|ACCESS_VIOLATION|access violation', re.I)


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))]


def row(name, fr):
    if not fr:
        print(f'  {name:18s} n=0')
        return
    w = [f[1] for f in fr]
    mean = st.mean(w)
    print(f'  {name:18s} n={len(fr):5d} fps={1000 / mean:6.1f} p50={pct(w, .5):7.1f} p95={pct(w, .95):7.1f} p99={pct(w, .99):7.1f} max={max(w):7.1f} '
          f'draws={st.median(f[3] for f in fr):6.0f} rec={st.mean(f[4] for f in fr):5.1f} wait={st.mean(f[5] for f in fr):5.1f} wait~84={sum(70 < f[5] < 100 for f in fr)}')


for d in map(Path, sys.argv[1:]):
    t = (d / 'stderr.log').read_text('utf-8', 'replace').splitlines()
    fr = []
    for l in t:
        m = RX.search(l)
        if m:
            fr.append((int(m[1]), float(m[2]), int(m[3]), int(m[4]), float(m[5]), float(m[6])))
    print(d.name, 'lines', len(t), 'frames', len(fr))
    first = next((i for i, f in enumerate(fr) if f[3] >= 700), None)
    if first is None:
        print('  never in race')
        continue
    race = fr[first:]
    print('  race from gframe', race[0][0], 'to', race[-1][0])
    row('race all', race)
    row('race light <700', [f for f in race if f[3] < 700])
    row('race heavy >=700', [f for f in race if f[3] >= 700])
    # the frames around the end hold the capture, drop the last 40
    row('race no tail', race[:-40])
    c = [l for l in t if 'vpc' in l.lower() and 'watch' in l.lower() or l.startswith('[VPC')]
    print('  c33 lines', len(c), '| first', c[1][:110] if len(c) > 1 else '', '| last', c[-1][:110] if c else '')
    b = [l for l in t if BAD.search(l)]
    print('  bad lines', len(b))
    for l in b[:6]:
        print('    ', l[:170])
    print('  vis-draw', sum(l.startswith('[vis-draw]') for l in t), 'vis-work', sum(l.startswith('[vis-work]') for l in t),
          'profile', [l[:120] for l in t if 'visual' in l.lower() and 'profile' in l.lower()][:2])
