"""Add arm X (Xx2): RSX_PIPE_MEMO=ab in-run A/B, dense on."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['W'] = ('r', {**ARMS['O'][1], 'RSX_VTX_DENSE': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['X'] = ('r', {**ARMS['O'][1], 'RSX_VTX_DENSE': '1', 'RSX_PIPE_MEMO': 'ab'})"
       "   # Xx2: exe 0dda46fb, Oo2 + dense + program memo switched on/off every 24 presents: [eng-ab]" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Ww2', 'Qq2', 'Yy1']", "'Ww2', 'Xx2', 'Qq2', 'Yy1']")
sub("MAX_LAUNCHES = 45", "MAX_LAUNCHES = 46")
sub("'N', 'O', 'Q', 'R', 'S', 'W'):", "'N', 'O', 'Q', 'R', 'S', 'W', 'X'):")
sub("PIN = 'bf5649ff2af838ecc4e109d8ac949d7593fbff167c213eba0eac3db8364b9f4c'   # ",
    "PIN = '0dda46fbfde22f2a63d5d706da925c922c08717bf5133413e18b159e9be531d1'   # RSX_PIPE_MEMO (+ab); ")
p.write_bytes(s.encode('utf-8'))
print('ok')
