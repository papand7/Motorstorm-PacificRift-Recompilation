"""Add arm O (Oo2) to ab2/run_vk.py: exe e8cf508c, shader window only."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['N'] = ('r', {**ARMS['I'][1], 'RSX_POLY_OFFSET'")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['O'] = ('r', {**ARMS['I'][1], 'RSX_POLY_OFFSET': '1', 'RSX_SHADER_WINDOW': '1'})"
       "   # Oo2: exe e8cf508c, Ii2 + polygon offset + WPOS in the guest shader window: fps and the tyre tracks, no dump" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Mm3', 'Nn2', 'Yy1']", "'Mm3', 'Nn2', 'Oo2', 'Yy1']")
sub("MAX_LAUNCHES = 39", "MAX_LAUNCHES = 40")
sub("'L', 'M', 'N'):", "'L', 'M', 'N', 'O'):")
p.write_bytes(s.encode('utf-8'))
print('ok')
