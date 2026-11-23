"""Add launch Kk26: Kk25's exe and configuration with the recording thread on throughout
(RSX_BE_THREAD=1), under sample_race.py SAMPLE_TOP=1 (sample_k26.json, map relinked from
4c22cb5e): where the walker's extra cycles go with the thread on (Kk23-Kk25: about 15% more).

usage: py -3 add_arm_k26.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', dict(ARMS['K'][1]))   # Kk25")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_BE_THREAD': '1'})"
       "   # Kk26: exe 4c22cb5e, Kk25 with the recording thread on throughout, under sample_race.py SAMPLE_TOP=1 (sample_k26.json)" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk24', 'Kk25', 'Yy1']", "'Kk24', 'Kk25', 'Kk26', 'Yy1']")
sub("MAX_LAUNCHES = 72", "MAX_LAUNCHES = 73")
p.write_bytes(s.encode('utf-8'))
print('ok')
