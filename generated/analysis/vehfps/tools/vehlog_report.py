r"""Report on a run's [vehlog] / [wdt] lines (RSX_VEHLOG, MSPR_DT_LOG; generated/analysis/vehfps).
Picks the drawn object nearest the camera in most frames (the player's vehicle), then per frame:
camera eye step |dE|, vehicle step |dT|, and the change of the vehicle's offset from the eye |dO|.
A vehicle updated every second frame shows |dT| ~ 0 on alternate frames while |dE| stays even.
usage: py -3 vehlog_report.py <stderr.log> [first frame] [last frame]"""
import collections
import math
import re
import statistics
import sys

RX = re.compile(r'\[vehlog\] f=(\d+) t=(\d+) draws=\d+/(\d+) cam=\d+ E=([-\d.e]+),([-\d.e]+),([-\d.e]+) \|(.*)')
RXO = re.compile(r' ([0-9A-F]{8})/c(\d+) ([-\d.e]+) ([-\d.e]+),([-\d.e]+),([-\d.e]+);')
RXW = re.compile(r'\[wdt\] n=(\d+) t=(\d+) dt=([-\d.e]+)')
path = sys.argv[1]
f0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
f1 = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 30
frames, wdt = [], []
for line in open(path, encoding='utf-8', errors='replace'):
    m = RX.search(line)
    if m:
        f = int(m.group(1))
        if f0 <= f <= f1:
            objs = [(o[0] + '/c' + o[1], float(o[2]), tuple(map(float, o[3:6]))) for o in RXO.findall(m.group(7))]
            frames.append((f, float(m.group(2)), tuple(float(m.group(i)) for i in (4, 5, 6)), objs))
        continue
    m = RXW.search(line)
    if m:
        wdt.append((float(m.group(2)), float(m.group(3))))
print(f'{len(frames)} vehlog frames, {len(wdt)} world steps')
if not frames:
    sys.exit()
near = collections.Counter(min(o, key=lambda x: x[1])[0] for _, _, _, o in frames if o)
key = near.most_common(1)[0][0]
print('nearest-object keys:', near.most_common(5))


def d3(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


rows = []
prev = None
for f, t, E, objs in frames:
    T = next((o[2] for o in objs if o[0] == key), None)
    if T is None:
        prev = None
        continue
    if prev and f == prev[0] + 1:
        rows.append((f, t - prev[1], d3(E, prev[2]), d3(T, prev[3]),
                     d3(tuple(a - b for a, b in zip(T, E)), tuple(a - b for a, b in zip(prev[3], prev[2]))), d3(T, E)))
    prev = (f, t, E, T)
print(f'{len(rows)} consecutive frame pairs with the vehicle ({key})')
moving = [r for r in rows if r[2] > 0.05]
print(f'{len(moving)} with the camera moving (|dE| > 0.05)')
if moving:
    still = sum(1 for r in moving if r[3] < 0.1 * r[2])
    print(f'vehicle step < 10% of the camera step: {still} of {len(moving)} ({100.0 * still / len(moving):.1f} %)')
    print('median ms between frames %.2f' % statistics.median(r[1] / 1000 for r in moving))
    print('median |dE| %.4f  |dT| %.4f  |dO| %.4f  dist %.3f' % tuple(statistics.median(r[i] for r in moving) for i in (2, 3, 4, 5)))
    rat = [r[3] / r[2] for r in moving]
    alt = [abs(rat[i] - rat[i - 1]) for i in range(1, len(rat))]
    print('median |dT|/|dE| %.3f, median change between neighbours %.3f' % (statistics.median(rat), statistics.median(alt)))
    print('first 40 moving pairs: frame, ms, |dE|, |dT|, |dO|, dist')
    for r in moving[:40]:
        print('  %6d %6.2f %.4f %.4f %.4f %.3f' % (r[0], r[1] / 1000, r[2], r[3], r[4], r[5]))
if wdt and moving:
    ws = sorted(w[0] for w in wdt)
    import bisect
    cnt = collections.Counter()
    for f, t, E, objs in frames:
        pass
    ts = [fr[1] for fr in frames]
    per = collections.Counter(bisect.bisect_left(ws, ts[i]) - bisect.bisect_left(ws, ts[i - 1]) for i in range(1, len(ts)))
    print('world steps between consecutive vehlog frames:', sorted(per.items())[:8])
    print('world dt median %.5f' % statistics.median(w[1] for w in wdt[-2000:]))
