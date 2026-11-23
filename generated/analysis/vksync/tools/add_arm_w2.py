"""Add arm W (Ww2) and pin exe bf5649ff (RSX_VTX_DENSE=ab in-run A/B)."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['S'] = ('r', {**ARMS['R'][1]})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['W'] = ('r', {**ARMS['O'][1], 'RSX_VTX_DENSE': 'ab'})"
       "   # Ww2: exe bf5649ff, Oo2 + dense vertex path switched on/off every 24 presents: [vtx-ab] RSX-thread cycles per present for each side" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Ss2', 'Qq2', 'Yy1']", "'Ss2', 'Ww2', 'Qq2', 'Yy1']")
sub("MAX_LAUNCHES = 44", "MAX_LAUNCHES = 45")
sub("'N', 'O', 'Q', 'R', 'S'):", "'N', 'O', 'Q', 'R', 'S', 'W'):")
sub("PIN = '2bbcd61a0a549b3e57ff60fc1fb3528cba580bde68eaa7e2f4073dc28dc6193d'   # ",
    "PIN = 'bf5649ff2af838ecc4e109d8ac949d7593fbff167c213eba0eac3db8364b9f4c'   # RSX_VTX_DENSE=ab; ")
p.write_bytes(s.encode('utf-8'))
print('ok')
