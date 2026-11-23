"""Add launch Kk14: Kk13 with the vertex decode on the GPU on throughout (RSX_VTX_GPU=1), exe f240ff32,
under sample_race.py (sample_k14.json): where the RSX thread's time goes once the CPU decode is gone."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines)
     if l.startswith("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'MSPR_PATCH'}, 'RSX_VTX_GPU': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_VTX_GPU': '1'})"
       "   # Kk14: exe f240ff32, Kk13 with the GPU vertex decode on throughout, under sample_race.py (sample_k14.json)" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk13', 'Yy1']", "'Kk13', 'Kk14', 'Yy1']")
sub("MAX_LAUNCHES = 60", "MAX_LAUNCHES = 61")
p.write_bytes(s.encode('utf-8'))
print('ok')
