"""Add launch Kk11: the Kk7 configuration (usleep exact, warm SPIR-V cache, memo on, [frame-hist]) with the
render-target readback asynchronous and synchronous by turns (RSX_RT_READBACK_ASYNC=ab), exe 942fc043:
does dropping the per-present GPU drain move the race frame?"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_PIPE_MEMO': '1'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_RT_READBACK_ASYNC': 'ab'})"
       "   # Kk11: exe 942fc043, Kk10 + async render-target readback on and off by turns ([eng-ab])" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk10', 'Yy1']", "'Kk10', 'Kk11', 'Yy1']")
sub("MAX_LAUNCHES = 57", "MAX_LAUNCHES = 58")
sub("PIN = '995f0f8db2e7285945779220b80573bb52c2ff193e8693d5cfd0238ce4fc0c12'   # ",
    "PIN = '942fc043efbec957729b01d7c7e60809676a573b25ed325424dfab332cf3637a'   # async RT readback (Kk11); ")
p.write_bytes(s.encode('utf-8'))
print('ok')
