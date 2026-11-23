"""Add launch Kk12: Kk11 with the asynchronous render-target readback on (it won its A/B in Kk11) and the
RPCS3 "Disable Dynamic Resolution Scaling" patch on and off by turns (MSPR_PATCH=drs:ab), exe 8eeeb235
([eng-vp] prints the scene viewport width for each side): does full resolution cost the frame anything?"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_RT_READBACK_ASYNC': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_RT_READBACK_ASYNC': '1', 'MSPR_PATCH': 'drs:ab'})"
       "   # Kk12: exe 8eeeb235, Kk11 with async readback on + no dynamic resolution on and off by turns ([eng-ab], [eng-vp])" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk11', 'Yy1']", "'Kk11', 'Kk12', 'Yy1']")
sub("MAX_LAUNCHES = 58", "MAX_LAUNCHES = 59")
sub("PIN = '942fc043efbec957729b01d7c7e60809676a573b25ed325424dfab332cf3637a'   # ",
    "PIN = '8eeeb235de73b1e53f8254b7354c06292fb51c33111109e5ea46ab5326ef0a29'   # MSPR_PATCH + [eng-vp] (Kk12); ")
p.write_bytes(s.encode('utf-8'))
print('ok')
