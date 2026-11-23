#!/usr/bin/env python3
"""Aggregate [m2] windows with t >= start_ms (race only): m2_agg.py stderr.log start_ms [fps]"""
import re, sys, collections
log, start = sys.argv[1], int(sys.argv[2]); fps = float(sys.argv[3]) if len(sys.argv) > 3 else 32.7
W = None; N = 0; cat = collections.Counter(); ex = collections.Counter(); self_ = collections.Counter(); rt = collections.Counter()
wait = collections.Counter(); incl = collections.Counter(); host = collections.Counter(); nwin = 0
for l in open(log, encoding='latin-1'):
    if not l.startswith('[m2]'): continue
    m = re.match(r'\[m2\] --- window t=(\d+)ms .*samples=(\d+)', l)
    if m:
        W = int(m.group(1)) >= start
        if W: N += int(m.group(2)); nwin += 1; cur = int(m.group(2))
        continue
    if not W: continue
    m = re.match(r'\[m2\] cat (\S+)\s+([\d.]+)%', l)
    if m: cat[m.group(1)] += float(m.group(2)) * cur / 100; continue
    m = re.match(r'\[m2\]\s+\d+\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+\d+ (\S+)', l)
    if m:
        n = m.group(7); f = cur / 100
        ex[n] += float(m.group(1)) * f; self_[n] += float(m.group(2)) * f; rt[n] += float(m.group(3)) * f
        continue
    m = re.match(r'\[m2\] incl\s+\d+\s+([\d.]+)%\s+(\S+)', l)
    if m: incl[m.group(2)] += float(m.group(1)) * cur / 100; continue
    m = re.match(r'\[m2\] waitin\s+\d+\s+([\d.]+)%\s+(\S+)', l)
    if m: wait[m.group(2)] += float(m.group(1)) * cur / 100; continue
    m = re.match(r'\[m2\] host(leaf|entry)\s+([\d.]+)%\s+(.*)', l)
    if m: host[m.group(1) + ' ' + m.group(3).strip()] += float(m.group(2)) * cur / 100
ft = 1000.0 / fps
print(f'windows {nwin}, samples {N}, frame {ft:.2f} ms ({fps} fps)')
for k, v in cat.items(): print(f'  cat {k:22s} {100*v/N:6.2f}%  {ft*v/N:6.2f} ms/frame')
print('top exclusive (self+rt+oth):')
cum = 0
for i, (n, v) in enumerate(ex.most_common(60)):
    cum += v
    print(f'  {i+1:3d} {n}  excl {100*v/N:5.2f}%  {ft*v/N:5.2f} ms  self {ft*self_[n]/N:5.2f}  rt {ft*rt[n]/N:5.2f}  incl {ft*incl[n]/N:5.2f} ms  cum {ft*cum/N:5.2f}')
print('top inclusive:')
for n, v in incl.most_common(200): print(f'  {n} {ft*v/N:6.2f} ms  (excl {ft*ex[n]/N:.2f})')
print('waits:')
for n, v in wait.most_common(12): print(f'  {n} {ft*v/N:6.2f} ms')
print('host:')
for n, v in host.most_common(30): print(f'  {n} {ft*v/N:6.2f} ms')
