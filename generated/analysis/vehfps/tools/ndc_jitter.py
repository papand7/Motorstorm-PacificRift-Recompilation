r"""Screen-space jitter of the player's vehicle (RSX_VEHLOG 'ndc x,y' of the nearest object's origin through the
frame's camera). In a chase camera its screen position should move smoothly; a 30 Hz component on 60 Hz frames
shows as hf = |p_n - (p_n-1 + p_n+1)/2| and a negative lag-1 correlation of dp. Also splits frames into
'renew' / 'hold' by parity to expose a 2-frame pattern. usage: py -3 ndc_jitter.py <stderr.log> [key]"""
import math
import re
import statistics
import sys

RX = re.compile(r'\[vehlog\] f=(\d+) t=\d+ .*?\|(.*)')
RXO = re.compile(r' ([0-9A-F]{8}/c\d+) ([-\d.e]+) [-\d.e]+,[-\d.e]+,[-\d.e]+ ndc ([-\d.e]+),([-\d.e]+);')
fr = []
for m in RX.finditer(open(sys.argv[1], encoding='utf-8', errors='replace').read()):
    fr.append((int(m.group(1)), {o[0]: (float(o[2]), float(o[3])) for o in RXO.findall(m.group(2))}))
keys = {}
for f, o in fr:
    for k in o:
        keys[k] = keys.get(k, 0) + 1
key = sys.argv[2] if len(sys.argv) > 2 else max(keys, key=keys.get)
seq = [(f, o[key]) for f, o in fr if key in o]
print('key', key, len(seq), 'frames of', len(fr))
hf, d1, d2 = [], [], []
for i in range(1, len(seq) - 1):
    (fa, a), (fb, b), (fc, c) = seq[i - 1], seq[i], seq[i + 1]
    if fa + 1 != fb or fb + 1 != fc:
        continue
    hf.append(math.hypot(b[0] - (a[0] + c[0]) / 2, b[1] - (a[1] + c[1]) / 2))
    d1.append((b[0] - a[0], b[1] - a[1])); d2.append((c[0] - b[0], c[1] - b[1]))
if hf:
    s = sorted(hf)
    print('screen hf (NDC units): median %.5f p90 %.5f p99 %.5f  (1 px at 1280 wide = %.5f)' % (
        statistics.median(hf), s[int(len(s) * 0.9)], s[int(len(s) * 0.99)], 2 / 1280))
    num = sum(p[0] * q[0] + p[1] * q[1] for p, q in zip(d1, d2))
    den = math.sqrt(sum(p[0] ** 2 + p[1] ** 2 for p in d1) * sum(q[0] ** 2 + q[1] ** 2 for q in d2))
    print('lag-1 correlation of dp: %.3f' % (num / den if den else 0))
    print('median |dp| %.5f' % statistics.median(math.hypot(*p) for p in d1))
