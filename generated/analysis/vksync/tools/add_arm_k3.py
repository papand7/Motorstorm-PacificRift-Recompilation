"""Add launch Kk3 in place of the never-launched Zz4: arm Z + the frame clock's FIFO kick on and off by turns
(PS3_FRAME_CLOCK_KICK=ab, timed by [eng-ab]), exe 1e610e77."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['Z'] = ('r', {**ARMS['O'][1], 'RSX_VTX_DENSE': '1', 'RSX_PIPE_MEMO': '1'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['Z'][1], 'PS3_FRAME_CLOCK_KICK': 'ab'})"
       "   # Kk3: exe 1e610e77, Zz3 + the frame clock woken by FIFO kicks on and off by turns ([eng-ab])" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Zz3', 'Zz4', 'Yy1']", "'Zz3', 'Kk3', 'Yy1']")
sub("'R', 'S', 'W', 'X', 'Z'):", "'R', 'S', 'W', 'X', 'Z', 'K'):")
sub("PIN = '439cd6a5fb7dac913964e6c848c7d6de3d083e898b8a37dece0ef03ec54e39ff'   # ",
    "PIN = '1e610e771a7ed74ae5ffedf1a4354eb85bc2c6d0d661ea73811cd05556760686'   # PS3_FRAME_CLOCK_KICK=ab (Kk3); ")
p.write_bytes(s.encode('utf-8'))
print('ok')
