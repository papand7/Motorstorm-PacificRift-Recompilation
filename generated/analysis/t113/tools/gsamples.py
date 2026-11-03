"""T113 arm E: per func_004C3778 call, the five G halves it read (func_00756E08 calls with lr inside it) and c."""
import re, struct, sys

rx = re.compile(r'\[PT\] t=(\d+) tid=\d+ ev=enter pc=00756E08 lr=([0-9A-F]{8}) .* r3=([0-9A-F]{8})')
rc = re.compile(r'\[PT\] t=(\d+) .*ev=enter pc=004C3778 .* m\[r3\+0x188\]=([0-9A-F]{8})')
calls, cur = [], None
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    m = rc.search(line)
    if m:
        cur = [int(m.group(1)) / 1e6, struct.unpack('>f', bytes.fromhex(m.group(2)))[0], []]; calls.append(cur); continue
    m = rx.search(line)
    if m and cur is not None and 0x4C3778 <= int(m.group(2), 16) < 0x4C3C00:
        h = int(m.group(3), 16) & 0xFFFF
        cur[2].append(struct.unpack(">e", struct.pack(">H", h))[0])
last = None
for t, c, g in calls:
    key = (int(t // 5), tuple(x == 0 for x in g))
    if key != last:
        print('t=%7.1f c_prev=%7.3f G=%s zeros=%d' % (t, c, ' '.join('%.4g' % x for x in g), sum(1 for x in g if x == 0)))
        last = key
