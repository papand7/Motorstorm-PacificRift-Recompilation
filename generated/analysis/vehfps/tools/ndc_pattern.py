"""Lag-1/lag-2 autocorrelation of the second difference of the nearest object's screen position (RSX_VEHLOG ndc).
A 2-frame step pattern gives ac1 ~ -0.5..-0.7 and ac2 > 0. usage: py -3 ndc_pattern.py <stderr.log> [key]"""
import re, sys, collections
txt = open(sys.argv[1], errors='replace').read()
RX = re.compile(r'\[vehlog\] f=(\d+) .*?\|(.*)')
RXO = re.compile(r' ([0-9A-F]{8}/c\d+) [-\d.e]+ [-\d.e]+,[-\d.e]+,[-\d.e]+ ndc ([-\d.e]+),([-\d.e]+);')
fr = [(int(m.group(1)), {o[0]: (float(o[1]), float(o[2])) for o in RXO.findall(m.group(2))}) for m in RX.finditer(txt)]
c = collections.Counter(k for _, o in fr for k in o)
key = sys.argv[2] if len(sys.argv) > 2 else c.most_common(1)[0][0]
s = [(f, o[key]) for f, o in fr if key in o]
sd = [(b[1][0] - (a[1][0] + cc[1][0]) / 2, b[1][1] - (a[1][1] + cc[1][1]) / 2) for a, b, cc in zip(s, s[1:], s[2:]) if a[0] + 1 == b[0] == cc[0] - 1]
def ac(v, l): return sum(v[i] * v[i + l] for i in range(len(v) - l)) / sum(t * t for t in v)
for ax in (0, 1):
    v = [q[ax] for q in sd]
    print('xy'[ax], 'n', len(v), 'ac1 %.3f ac2 %.3f rms %.5f' % (ac(v, 1), ac(v, 2), (sum(t * t for t in v) / len(v)) ** 0.5))
