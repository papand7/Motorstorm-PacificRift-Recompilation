r"""High-frequency jitter of the vehicle's offset from the camera eye (RSX_VEHLOG), split by the world dt
of the frame (MSPR_DT_LOG, matched by order: one world step per vehlog frame). hf = |O_n - (O_n-1 + O_n+1)/2|.
Also the lag-1 correlation of dO (negative = alternating, a 30 Hz step pattern on a 60 Hz frame).
usage: py -3 offset_jitter.py <stderr.log> [key]"""
import bisect
import math
import re
import statistics
import sys

RX = re.compile(r'\[vehlog\] f=(\d+) t=(\d+) draws=\d+/\d+ cam=\d+ E=([-\d.e]+),([-\d.e]+),([-\d.e]+) \|(.*)')
RXO = re.compile(r' ([0-9A-F]{8}/c\d+) ([-\d.e]+) ([-\d.e]+),([-\d.e]+),([-\d.e]+);')
RXW = re.compile(r'\[wdt\] n=\d+ t=(\d+) dt=([-\d.e]+)')
txt = open(sys.argv[1], encoding='utf-8', errors='replace').read()
fr = []
for m in RX.finditer(txt):
    objs = {o[0]: tuple(map(float, o[2:5])) for o in RXO.findall(m.group(6))}
    fr.append((int(m.group(1)), float(m.group(2)), tuple(map(float, m.group(3, 4, 5))), objs))
ws = [(float(a), float(b)) for a, b in RXW.findall(txt)]
wt = [w[0] for w in ws]
key = sys.argv[2] if len(sys.argv) > 2 else max({k for f in fr for k in f[3]}, key=lambda k: sum(k in f[3] for f in fr))
seq = []
for f, t, E, o in fr:
    if key in o:
        i = bisect.bisect_left(wt, t) - 1   # the world step before this frame's first draw
        dt = ws[i][1] if i >= 0 else 0.0
        seq.append((f, t, tuple(a - b for a, b in zip(o[key], E)), dt, E, o[key]))
print('key', key, len(seq), 'frames')
groups = {'dt<0.0332 (hold on)': [], 'dt>=0.0332': []}
d1 = []
for i in range(1, len(seq) - 1):
    a, b, c = seq[i - 1], seq[i], seq[i + 1]
    if not (a[0] + 1 == b[0] and b[0] + 1 == c[0]):
        continue
    hf = math.sqrt(sum((b[2][k] - (a[2][k] + c[2][k]) / 2) ** 2 for k in range(3)))
    groups['dt<0.0332 (hold on)' if b[3] < 1 / 30 - 1e-4 else 'dt>=0.0332'].append(hf)
    d1.append((tuple(b[2][k] - a[2][k] for k in range(3)), tuple(c[2][k] - b[2][k] for k in range(3))))
for g, v in groups.items():
    if v:
        print(f'{g}: n={len(v)} median hf {statistics.median(v):.4f} p90 {sorted(v)[int(len(v) * 0.9)]:.4f}')
if d1:
    num = sum(sum(x * y for x, y in zip(p, q)) for p, q in d1)
    den = math.sqrt(sum(sum(x * x for x in p) for p, _ in d1) * sum(sum(y * y for y in q) for _, q in d1))
    print('lag-1 correlation of dO: %.3f' % (num / den if den else 0))
