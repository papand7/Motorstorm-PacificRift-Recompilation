"""Add launch Kk47: Kk46 on the build with a per-monitor DPI-aware window under RSX_RES_SCALE (the 1920x1080 client area was clamped to 1711x941 on the 150 % desktop). Kk46 note follows.
rounded outwards to whole host texels (Kk44 showed a dark band at the bottom of the frame).

usage: py -3 add_arm_k46.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk46: ' in l][0]
lines.insert(i + 1, "ARMS['K'] = ('r', dict(ARMS['K'][1]))"
                    "   # Kk47: exe %s, Kk46 on the DPI-aware window build" % pin[:8])
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk45', 'Kk46', 'Yy1']", "'Kk45', 'Kk46', 'Kk47', 'Yy1']")
sub("MAX_LAUNCHES = 93", "MAX_LAUNCHES = 94")
sub("PIN = '03a8df66c930031f99f36a3524926e2b4356dac0b04cddf0f6062077d1da211c'   # ",
    "PIN = '%s'   # RSX_RES_SCALE DPI-aware window (Kk47); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
