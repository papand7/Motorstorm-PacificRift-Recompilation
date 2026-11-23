"""Add arm R (Rr2) to ab2/run_vk.py and pin exe eed0a668 (RSX_VTX_DENSE)."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['Q'] = ('r', {**ARMS['O'][1]")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['R'] = ('r', {**ARMS['O'][1], 'RSX_VTX_DENSE': '1'})"
       "   # Rr2: exe eed0a668, Oo2 + dense vertex runs (no hash remap, column decode), under sample_race.py" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Ii3', 'Qq2', 'Yy1']", "'Ii3', 'Rr2', 'Qq2', 'Yy1']")
sub("MAX_LAUNCHES = 42", "MAX_LAUNCHES = 43")
sub("'N', 'O', 'Q'):", "'N', 'O', 'Q', 'R'):")
sub("PIN = 'e8cf508ceac2f2cda3cc314bf1df7d11aba3a3f49365dc11ab6fbac29b8ba1e4'   # ",
    "PIN = 'eed0a66814d62174fbf7df22533d2823cf75b553df9859c8bdf1c1d02239c2ac'   # RSX_VTX_DENSE; ")
p.write_bytes(s.encode('utf-8'))
print('ok')
