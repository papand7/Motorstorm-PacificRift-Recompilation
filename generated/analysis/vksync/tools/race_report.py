"""Race summary of one vk run: frames per second from [rsx-hb] (all presents, and presents that drew),
the [frame-hist] windows of the race, and what [vk-compile] added during the race.
usage: race_report.py <run dir> <controller.log>"""
import re
import sys

run, ctl = sys.argv[1], sys.argv[2]
r = int(re.search(r'race_entry \{"hb_ms": (\d+)', open(ctl, errors='ignore').read())[1])
L = open(run + '/stderr.log', errors='ignore').read().split('\n')
hb_ms = 0
hb, hist, comp = [], [], []
for line in L:
    m = re.search(r'\[rsx-hb\] ms=(\d+) frames=(\d+) draw_frames=(\d+)', line)
    if m:
        hb_ms = int(m[1])
        hb.append(tuple(map(int, m.groups())))
    if hb_ms >= r and '[frame-hist]' in line:
        hist.append(line.strip())
    m = re.search(r'\[vk-compile\] spirv=(\d+)/([\d.]+)ms variants=(\d+)/([\d.]+)ms translations=(\d+) disk_hits=(\d+)', line)
    if m:
        comp.append((hb_ms, [float(x) for x in m.groups()]))
w = [h for h in hb if h[0] >= r + 5000]
if len(w) > 1:
    dt = (w[-1][0] - w[0][0]) / 1000
    print(f'race {dt:.0f} s: presents/s {(w[-1][1] - w[0][1]) / dt:.1f}, drawing presents/s {(w[-1][2] - w[0][2]) / dt:.1f}')
for h in hist:
    print(' ', h)
before = [c for c in comp if c[0] < r]
during = [c for c in comp if c[0] >= r]
if before and during:
    a, b = before[-1][1], during[-1][1]
    print(f'race compile: spirv {b[0] - a[0]:.0f} / {b[1] - a[1]:.0f} ms, variants {b[2] - a[2]:.0f} / {b[3] - a[3]:.0f} ms, '
          f'translations {b[4] - a[4]:.0f}, disk hits {b[5] - a[5]:.0f}')
if comp:
    c = comp[-1][1]
    print(f'whole run: spirv {c[0]:.0f} / {c[1]:.0f} ms, variants {c[2]:.0f} / {c[3]:.0f} ms, translations {c[4]:.0f}, disk hits {c[5]:.0f}')
