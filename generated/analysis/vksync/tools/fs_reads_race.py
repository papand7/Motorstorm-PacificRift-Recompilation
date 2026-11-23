"""cellFs read volume per descriptor in a race, and re-reads of one descriptor, from a run logged with
FS_READ_ALL=1 (every '[fs] read fd=..' line) and PS3_FSLOG_READS=<fd> ('[fsread] .. pos=..' lines).
Lines are clocked by the preceding '[rsx-hb] ms=' heartbeat; the race starts at the controller's
race_entry hb_ms.

usage: py -3 fs_reads_race.py <run dir (generated/runs/..)> <runtime dir (ab2/runtime-..)>"""
import collections
import json
import re
import sys
from pathlib import Path

run, rt = Path(sys.argv[1]), Path(sys.argv[2])
entry = None
for line in (rt / 'controller.log').read_text(errors='replace').splitlines():
    if 'race_entry' in line:
        entry = json.loads(line.split('race_entry', 1)[1])['hb_ms']
        break
assert entry is not None, 'no race_entry'
rx_hb = re.compile(r'^\[rsx-hb\] ms=(\d+)')
rx_rd = re.compile(r'^\[fs\] read fd=(\d+) nbytes=(\d+) -> (\d+)')
rx_pos = re.compile(r'^\[fsread\] fd=(\d+) want=(\d+) got=(\d+) pos=(-?\d+)')
hb = 0
last_hb = 0
per = collections.defaultdict(lambda: [0, 0])
spans = []
for line in open(run / 'stderr.log', encoding='utf-8', errors='replace'):
    m = rx_hb.match(line)
    if m:
        hb = int(m.group(1))
        last_hb = max(last_hb, hb)
        continue
    if hb < entry:
        continue
    m = rx_rd.match(line)
    if m:
        c = per[int(m.group(1))]
        c[0] += 1
        c[1] += int(m.group(3))
        continue
    m = rx_pos.match(line)
    if m:
        spans.append((int(m.group(4)), int(m.group(3))))
secs = max(1e-3, (last_hb - entry) / 1000)
print(f'race window {secs:.1f} s (hb {entry} .. {last_hb})')
for fd, (n, b) in sorted(per.items()):
    print(f'  fd {fd}: {n} reads, {b / 1e6:.1f} MB, {b / 1e6 / secs:.2f} MB/s, {b / max(1, n) / 1024:.1f} KB a read')
if spans:
    tot = sum(g for _, g in spans)
    cover = collections.Counter()
    for pos, got in spans:
        for blk in range(pos // 65536, (pos + max(got, 1) - 1) // 65536 + 1):
            cover[blk] += 1
    uniq = len(cover) * 65536
    reread = sum(1 for v in cover.values() if v > 1)
    print(f'  traced fd: {len(spans)} reads, {tot / 1e6:.1f} MB; distinct 64 KB blocks {len(cover)} '
          f'({uniq / 1e6:.1f} MB); blocks read more than once {reread}; max reads of one block '
          f'{max(cover.values())}')
    lo, hi = min(p for p, _ in spans), max(p + g for p, g in spans)
    print(f'  traced fd offset range {lo / 1e6:.1f} .. {hi / 1e6:.1f} MB')
