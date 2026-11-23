"""Sum [samp] main-thread reports after race entry (t >= T0 ms). usage: samp_sum.py <stderr.log> <t0_ms>"""
import sys, re, collections
t, t0, c, tot = 0, float(sys.argv[2]), collections.Counter(), 0
for l in open(sys.argv[1], encoding='latin-1'):
    m = re.match(r'\[samp\] --- report at t=(\d+)ms', l)
    if m: t = int(m.group(1)); continue
    if t < t0: continue
    m = re.match(r'\[samp\]\s+[\d.]+%\s+(\S+)\s+\((\d+)\)', l)
    if m: c[m.group(1)] += int(m.group(2))
    m = re.match(r'\[samp\] (\d+) samples', l)
    if m: tot += int(m.group(1))
print('samples', tot)
for k, v in c.most_common(25): print('%6.2f%%  %s' % (100.0 * v / tot, k))
