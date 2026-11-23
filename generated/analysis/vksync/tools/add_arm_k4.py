"""Add launch Kk4: arm Z + guest usleep exact (PS3_USLEEP_SPIN=2) and on the timer by turns
(PS3_USLEEP_SPIN=ab, timed by [eng-ab]), exe 64479d84."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['Z'][1], 'PS3_FRAME_CLOCK_KICK': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['Z'][1], 'PS3_USLEEP_SPIN': 'ab'})"
       "   # Kk4: exe 64479d84, Zz4 + guest usleep exact and on the host timer by turns ([eng-ab])" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Zz4', 'Yy1']", "'Zz4', 'Kk4', 'Yy1']")
sub("MAX_LAUNCHES = 50", "MAX_LAUNCHES = 51")
sub("PIN = '1e610e771a7ed74ae5ffedf1a4354eb85bc2c6d0d661ea73811cd05556760686'   # ",
    "PIN = '64479d84c7e55ecaf486f7039377c4f40a1353f9febf6822f0d1b97c097654a5'   # PS3_USLEEP_SPIN=ab (Kk4); ")
p.write_bytes(s.encode('utf-8'))
print('ok')
