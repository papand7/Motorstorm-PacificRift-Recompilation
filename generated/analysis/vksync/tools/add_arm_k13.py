"""Add launch Kk13: Kk12 without the dynamic-resolution patch (no effect in Kk12) and with vertex
columns decoded on the GPU on and off by turns (RSX_VTX_GPU=ab), exe f240ff32: does moving the
vertex decode off the RSX thread move the race frame? [vk-vtxgpu] counts what went to the GPU."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines)
     if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_RT_READBACK_ASYNC': '1', 'MSPR_PATCH': 'drs:ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'MSPR_PATCH'}, 'RSX_VTX_GPU': 'ab'})"
       "   # Kk13: exe f240ff32, Kk12 without MSPR_PATCH + vertex decode on the GPU on and off by turns ([eng-ab], [vk-vtxgpu])" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk12', 'Yy1']", "'Kk12', 'Kk13', 'Yy1']")
sub("MAX_LAUNCHES = 59", "MAX_LAUNCHES = 60")
sub("PIN = '8eeeb235de73b1e53f8254b7354c06292fb51c33111109e5ea46ab5326ef0a29'   # ",
    "PIN = 'f240ff32b8795d0e5d526d51c4fd0a3eca31898dcedcc3aded7b40ec2651ffbc'   # RSX_VTX_GPU (Kk13); ")
p.write_bytes(s.encode('utf-8'))
print('ok')
