"""Add launch Kk17: Kk16 without the FIFO kick (no gain in Kk16), i.e. the Kk14 configuration on
exe 0506ee54, under sample_race.py with SAMPLE_TOP=1 (sample_k17.json, 80 entries per thread):
the whole cost of the RSX drain, which Kk15's trace put on the frame's critical path."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k not in ('PS3_VM_STORE_INLINE'")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'PS3_FRAME_CLOCK_KICK'})"
       "   # Kk17: exe 0506ee54, the Kk14 configuration under sample_race.py SAMPLE_TOP=1 (sample_k17.json)" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk16', 'Yy1']", "'Kk16', 'Kk17', 'Yy1']")
sub("MAX_LAUNCHES = 63", "MAX_LAUNCHES = 64")
p.write_bytes(s.encode('utf-8'))
print('ok')
