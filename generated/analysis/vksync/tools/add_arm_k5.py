"""Add launch Kk5: arm Z + guest usleep exact for the whole run (PS3_USLEEP_SPIN=2) + the frame-time
histogram (RSX_FRAME_HIST=1), exe f4a436b7: is 30 fps held?"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['Z'][1], 'PS3_USLEEP_SPIN': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['Z'][1], 'PS3_USLEEP_SPIN': '2', 'RSX_FRAME_HIST': '1'})"
       "   # Kk5: exe f4a436b7, Zz4 + guest usleep exact all run + [frame-hist]" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk4', 'Yy1']", "'Kk4', 'Kk5', 'Yy1']")
sub("MAX_LAUNCHES = 51", "MAX_LAUNCHES = 52")
sub("PIN = '64479d84c7e55ecaf486f7039377c4f40a1353f9febf6822f0d1b97c097654a5'   # ",
    "PIN = 'f4a436b7f794eb9561650fa67b0c214721b92c719ec0e7a86c75cc1b3db86069'   # RSX_FRAME_HIST (Kk5); ")
p.write_bytes(s.encode('utf-8'))
print('ok')
