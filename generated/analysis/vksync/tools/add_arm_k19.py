"""Add launch Kk19: Kk18's configuration on exe ffc242c3, where GCM_FIFO_FAST is on by default
(the variable is dropped, so the default is what runs), under sample_race.py with SAMPLE_TOP=1
(sample_k19.json, 80 entries per thread): what the RSX thread still spends per frame, and what
of it could move to the GPU.

usage: py -3 add_arm_k19.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'GCM_FIFO_FAST': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'GCM_FIFO_FAST'})"
       "   # Kk19: exe %s (GCM_FIFO_FAST on by default), under sample_race.py SAMPLE_TOP=1 (sample_k19.json)" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk18', 'Yy1']", "'Kk18', 'Kk19', 'Yy1']")
sub("MAX_LAUNCHES = 65", "MAX_LAUNCHES = 66")
sub("PIN = '1e7da189ad4b84dd6d483fd3f4901cf744b71e64d40ab0356e84ff8a1f44901e'   # ",
    "PIN = '%s'   # GCM_FIFO_FAST default (Kk19); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
