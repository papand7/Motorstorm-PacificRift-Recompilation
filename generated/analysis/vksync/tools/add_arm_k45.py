"""Add launch Kk45: Kk44 at scale 1 (RSX_RES_SCALE removed), same exe: the comparison pictures for the
1.5x race, and the res-scale build's scale-1 path in a race.

usage: py -3 add_arm_k45.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk44: ' in l][0]
lines.insert(i + 1, "ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'RSX_RES_SCALE'})"
                    "   # Kk45: exe fe394f8a, Kk44 at scale 1 (comparison pictures)")
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk43', 'Kk44', 'Yy1']", "'Kk43', 'Kk44', 'Kk45', 'Yy1']")
sub("MAX_LAUNCHES = 91", "MAX_LAUNCHES = 92")
p.write_bytes(s.encode('utf-8'))
print('ok')
