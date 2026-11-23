"""Add arm Z (Zz2): dense + program memo on, profiled."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['X'] = ('r', {**ARMS['O'][1], 'RSX_VTX_DENSE': '1', 'RSX_PIPE_MEMO': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['Z'] = ('r', {**ARMS['O'][1], 'RSX_VTX_DENSE': '1', 'RSX_PIPE_MEMO': '1'})"
       "   # Zz2: exe 0dda46fb, Oo2 + dense + program memo, under sample_race.py (sample_z2.json)" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Xx2', 'Qq2', 'Yy1']", "'Xx2', 'Zz2', 'Qq2', 'Yy1']")
sub("MAX_LAUNCHES = 46", "MAX_LAUNCHES = 47")
sub("'N', 'O', 'Q', 'R', 'S', 'W', 'X'):", "'N', 'O', 'Q', 'R', 'S', 'W', 'X', 'Z'):")
p.write_bytes(s.encode('utf-8'))
print('ok')
