"""Add launch Kk46: Kk44 (RSX_RES_SCALE=1.5, no dynamic resolution) on the build whose viewport is
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
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk45: ' in l][0]
lines.insert(i + 1, "ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_RES_SCALE': '1.5'})"
                    "   # Kk46: exe %s, Kk44 with the viewport rounded to whole host texels" % pin[:8])
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk44', 'Kk45', 'Yy1']", "'Kk44', 'Kk45', 'Kk46', 'Yy1']")
sub("MAX_LAUNCHES = 92", "MAX_LAUNCHES = 93")
sub("PIN = 'fe394f8aa3f70ef27b6543bb6e2ac71fc5687337bc46a09749eb3bac54360f93'   # ",
    "PIN = '%s'   # RSX_RES_SCALE viewport rounding (Kk46); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
