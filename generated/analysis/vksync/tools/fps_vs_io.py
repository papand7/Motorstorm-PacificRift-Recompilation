"""Presents per second (from the cumulative '[vk-waits] ... present=N/' count, clocked by the preceding
'[rsx-hb] ms=' heartbeat) next to the file read rate of io_rate.py, in buckets after race entry.

usage: py -3 fps_vs_io.py <run dir> <runtime dir> <io_rate.txt> [bucket_s=15]"""
import json
import re
import sys
from pathlib import Path

run, rt, io = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
B = float(sys.argv[4]) if len(sys.argv) > 4 else 15.0
entry = None
for line in (rt / 'controller.log').read_text(errors='replace').splitlines():
    if 'race_entry' in line:
        entry = json.loads(line.split('race_entry', 1)[1])['hb_ms'] / 1000
        break
rx_hb = re.compile(r'^\[rsx-hb\] ms=(\d+)')
rx_pr = re.compile(r'^\[vk-waits\].* present=(\d+)/')
hb, pts = 0, []
for line in open(run / 'stderr.log', encoding='utf-8', errors='replace'):
    m = rx_hb.match(line)
    if m:
        hb = int(m.group(1)) / 1000
        continue
    m = rx_pr.match(line)
    if m and hb:
        pts.append((hb, int(m.group(1))))
rd = []
for line in io.read_text().splitlines():
    p = line.split()
    if len(p) >= 2:
        rd.append((float(p[0]), float(p[1])))
print(f'race entry {entry:.1f} s; bucket {B:.0f} s')
print(' from_s   to_s   fps   ms/present   read MB/s')
t = entry
while t + B <= pts[-1][0]:
    a = [p for p in pts if t <= p[0] < t + B]
    if len(a) >= 2:
        fps = (a[-1][1] - a[0][1]) / (a[-1][0] - a[0][0])
        r = [v for s, v in rd if t <= s < t + B]
        print(f'{t - entry:6.0f} {t + B - entry:6.0f} {fps:6.1f} {1000 / max(fps, 1e-3):9.1f}   '
              f'{(sum(r) / len(r)) if r else float("nan"):8.1f}')
    t += B
