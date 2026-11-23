"""Add launch Kk30: a second repeat of Kk28 (Kk29 ran under heavy PC load) (same exe 84ee1a83, PS3_VMX_FAST=ab), to replicate its
in-run A/B (fast paths on 50.20 vs off 51.28 ms a present over 5 race windows).

usage: py -3 add_arm_k30.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', dict(ARMS['K'][1]))   # Kk29")][0]
eol = '\r' if lines[i].endswith('\r') else ''
lines.insert(i + 1, "ARMS['K'] = ('r', dict(ARMS['K'][1]))   # Kk30: exe 84ee1a83, a second repeat of Kk28" + eol)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk28', 'Kk29', 'Yy1']", "'Kk28', 'Kk29', 'Kk30', 'Yy1']")
sub("MAX_LAUNCHES = 76", "MAX_LAUNCHES = 77")
p.write_bytes(s.encode('utf-8'))
print('ok')
