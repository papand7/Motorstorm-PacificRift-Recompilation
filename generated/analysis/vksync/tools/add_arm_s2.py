"""Add arm S (Ss2) and pin exe 2bbcd61a (dense index read)."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['R'] = ('r', {**ARMS['O'][1]")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['S'] = ('r', {**ARMS['R'][1]})"
       "   # Ss2: exe 2bbcd61a, Rr2 + index runs read in one loop; under sample_chain.py (what the main thread polls)" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Rr2', 'Qq2', 'Yy1']", "'Rr2', 'Ss2', 'Qq2', 'Yy1']")
sub("MAX_LAUNCHES = 43", "MAX_LAUNCHES = 44")
sub("'N', 'O', 'Q', 'R'):", "'N', 'O', 'Q', 'R', 'S'):")
sub("PIN = 'eed0a66814d62174fbf7df22533d2823cf75b553df9859c8bdf1c1d02239c2ac'   # ",
    "PIN = '2bbcd61a0a549b3e57ff60fc1fb3528cba580bde68eaa7e2f4073dc28dc6193d'   # dense index read; ")
p.write_bytes(s.encode('utf-8'))
print('ok')
